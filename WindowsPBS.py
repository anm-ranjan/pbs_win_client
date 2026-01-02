#!/usr/bin/env python3
"""
PBS PRO Job Monitor and Submitter
Windows CLI tool to monitor and submit jobs across multiple Linux servers
"""

import paramiko
import json
import sys
import os
import time
import shutil
import yaml
from collections import OrderedDict
from getpass import getuser
from pathlib import Path


def load_config(config_path=None):
    """
    Load configuration from YAML file.
    
    Args:
        config_path: Path to config file. If None, searches in:
                     1. ./config.yaml
                     2. ~/.pbs_monitor/config.yaml
                     3. Script directory/config.yaml
    
    Returns:
        dict: Configuration dictionary
    """
    search_paths = []
    
    if config_path:
        search_paths.append(config_path)
    else:
        # Current directory
        search_paths.append(Path("./config.yaml"))
        # User's home directory
        search_paths.append(Path.home() / ".pbs_monitor" / "config.yaml")
        # Script directory
        search_paths.append(Path(__file__).parent / "config.yaml")
    
    for path in search_paths:
        if Path(path).exists():
            try:
                with open(path, 'r') as f:
                    config = yaml.safe_load(f)
                print(f"✓ Loaded configuration from: {path}")
                return config
            except yaml.YAMLError as e:
                print(f"❌ Error parsing config file {path}: {e}")
                sys.exit(1)
    
    print("❌ Configuration file not found!")
    print("   Searched in:")
    for path in search_paths:
        print(f"   - {path}")
    print("\n   Please create a config.yaml file.")
    sys.exit(1)


def validate_config(config):
    """Validate that all required configuration keys are present."""
    required_keys = {
        'pbs': ['qdel_path', 'qsub_path', 'submit_script_name'],
        'paths': ['linux_base_path', 'remote_script_name'],
        'drive_mapping': None,  # Just needs to exist
        'servers': None  # Just needs to exist and be a list
    }
    
    errors = []
    
    for section, keys in required_keys.items():
        if section not in config:
            errors.append(f"Missing section: '{section}'")
            continue
        
        if keys:
            for key in keys:
                if key not in config[section]:
                    errors.append(f"Missing key: '{section}.{key}'")
    
    # Validate servers is a list with required fields
    if 'servers' in config:
        if not isinstance(config['servers'], list):
            errors.append("'servers' must be a list")
        elif len(config['servers']) == 0:
            errors.append("'servers' list cannot be empty")
        else:
            for i, server in enumerate(config['servers']):
                if 'hostname' not in server:
                    errors.append(f"Server {i+1}: missing 'hostname'")
                if 'name' not in server:
                    errors.append(f"Server {i+1}: missing 'name'")
    
    # Validate drive_mapping is a dict
    if 'drive_mapping' in config:
        if not isinstance(config['drive_mapping'], dict):
            errors.append("'drive_mapping' must be a dictionary")
        elif len(config['drive_mapping']) == 0:
            errors.append("'drive_mapping' cannot be empty")
    
    if errors:
        print("❌ Configuration validation errors:")
        for error in errors:
            print(f"   - {error}")
        sys.exit(1)
    
    return True


class PBSJobManager:
    def __init__(self, config, user):
        """
        Initialize with configuration and username.
        
        Args:
            config: Configuration dictionary from YAML
            user: Current username for SSH connections
        """
        self.config = config
        self.user = user
        self.all_jobs = []
        
        # Extract PBS configuration values
        self.qdel_path = config['pbs']['qdel_path']
        self.qsub_path = config['pbs']['qsub_path']
        self.submit_script_name = config['pbs']['submit_script_name']
        
        # Extract path configuration values
        self.linux_base_path = config['paths']['linux_base_path']
        self.remote_script_name = config['paths']['remote_script_name']
        
        # Extract drive mapping
        self.drive_mapping = config['drive_mapping']
        
        # SSH configuration
        self.ssh_timeout = config.get('ssh', {}).get('connection_timeout', 10)
        
        # Create reverse mapping: server hostname -> drive letter
        self.server_to_drive = {hostname: drive for drive, hostname in self.drive_mapping.items()}
        
        # Setup servers with username and key_file
        self.servers = self._setup_servers(config['servers'])
        
        # Calculate script paths
        self.script_dir = f"{self.linux_base_path}/{self.user}"
        self.script_path = f"{self.script_dir}/{self.remote_script_name}"
    
    def _setup_servers(self, servers_config):
        """Add username and key_file to server configurations."""
        # Get user's home directory for SSH key
        user_home = os.path.expanduser("~")
        default_key_path = os.path.join(user_home, ".ssh", "id_rsa")
        
        # Check for config override or default key
        config_key = self.config.get('ssh', {}).get('key_file', '')
        
        if config_key and os.path.exists(config_key):
            use_key = config_key
            print(f"🔑 Using SSH key from config: {use_key}")
        elif os.path.exists(default_key_path):
            use_key = default_key_path
            print(f"🔑 Found SSH key: {default_key_path}")
        else:
            use_key = None
            print(f"⚠️  No SSH key found. You may be prompted for passwords.")
        
        servers = []
        for srv in servers_config:
            server = {
                'hostname': srv['hostname'],
                'name': srv['name'],
                'username': self.user,
                'key_file': use_key
            }
            servers.append(server)
        
        return servers
    
    def connect_and_execute(self, server, command):
        """Execute command on remote server via SSH"""
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            # Connect using SSH key or password
            if 'key_file' in server and server['key_file']:
                ssh.connect(
                    server['hostname'],
                    username=server['username'],
                    key_filename=server['key_file'],
                    timeout=self.ssh_timeout
                )
            else:
                ssh.connect(
                    server['hostname'],
                    username=server['username'],
                    timeout=self.ssh_timeout
                )
            
            stdin, stdout, stderr = ssh.exec_command(command)
            output = stdout.read().decode('utf-8')
            error = stderr.read().decode('utf-8')
            
            ssh.close()
            
            if error and not output:
                print(f"Error from {server['hostname']}: {error}")
                return None
            
            return output
            
        except Exception as e:
            print(f"Connection error to {server['hostname']}: {str(e)}")
            return None
    
    def parse_output(self, output, server_name):
        """Parse the JSON output from the Python script"""
        try:
            jobs_data = json.loads(output)
            jobs = []
            
            for job_data in jobs_data:
                job = OrderedDict([
                    ('Server', server_name),
                    ('JobID', job_data.get('JobID', 'N/A')),
                    ('Job_Name', job_data.get('Job_Name', 'N/A')),
                    ('Job_Path', job_data.get('Job_Path', 'N/A')),
                    ('CPUs', str(job_data.get('CPUs', 'N/A'))),
                    ('Status', job_data.get('Status', 'N/A')),
                    ('Owner', job_data.get('Owner', 'N/A')),
                    ('Memory', job_data.get('Memory', 'N/A'))
                ])
                jobs.append(job)
            
            return jobs
            
        except json.JSONDecodeError as e:
            print(f"Error parsing JSON from {server_name}: {str(e)}")
            return []
    
    def fetch_all_jobs(self):
        """Fetch jobs from all servers"""
        self.all_jobs = []
        
        print("\n🔄 Fetching jobs from all servers...\n")
        
        for server in self.servers:
            print(f"📡 Connecting to {server['name']}...", end=' ')
            
            command = f"python3 {self.script_path} --json"
            output = self.connect_and_execute(server, command)
            
            if output:
                jobs = self.parse_output(output, server['name'])
                self.all_jobs.extend(jobs)
                print(f"✓ Found {len(jobs)} jobs")
            else:
                print("✗ Failed")
        
        print(f"\n📊 Total jobs found: {len(self.all_jobs)}\n")
        return self.all_jobs
    
    def display_jobs(self, jobs=None, sort_by='JobID'):
        """Display jobs in a formatted table"""
        if jobs is None:
            jobs = self.all_jobs
        
        if not jobs:
            print("❌ No jobs to display\n")
            return
        
        # Sort jobs
        if sort_by in ['CPUs']:
            jobs = sorted(jobs, key=lambda x: int(x[sort_by]) if x[sort_by].isdigit() else 0)
        else:
            jobs = sorted(jobs, key=lambda x: x[sort_by])
        
        # Define column widths
        widths = {
            'Server': 20,
            'JobID': 35,
            'Job_Name': 30,
            'Job_Path': 50,
            'CPUs': 6,
            'Status': 8,
            'Owner': 10,
            'Memory': 10
        }
        
        # Print header
        header = ""
        separator = ""
        for field, width in widths.items():
            header += f"{field:<{width}} "
            separator += "-" * width + " "
        
        print(header)
        print(separator)
        
        # Print jobs
        for job in jobs:
            row = ""
            for field, width in widths.items():
                value = job.get(field, 'N/A')
                if len(value) > width - 1:
                    value = value[:width-4] + "..."
                row += f"{value:<{width}} "
            print(row)
        
        print()
    
    def kill_job(self, job_id, server_hostname=None):
        """Kill a job on specified server"""
        # If server not specified, try to find it from job list
        job_path = ""
        if not server_hostname:
            for job in self.all_jobs:
                if job_id in job['JobID']:
                    server_hostname = job['Server']
                    job_path = job['Job_Path']
                    break
        
        if not server_hostname:
            print(f"❌ Could not determine server for job {job_id}")
            return False
        
        # Find the server config
        server = None
        for s in self.servers:
            if s['name'] == server_hostname:
                server = s
                break
        
        if not server:
            print(f"❌ Server {server_hostname} not found in configuration")
            return False
        
        print(f"\n🗑️  Killing job {job_id} on {server_hostname}...")
        
        command = f"{self.qdel_path} {job_id}"
        output = self.connect_and_execute(server, command)
        
        if output is not None:
            print(f"✓ Job {job_id} killed successfully!")
            if output.strip():
                print(f"  Output: {output.strip()}")
            del_dir = input("\nDelete job directory (y/n): ").strip()
            if del_dir == 'y':
                command = f"rm -rf {job_path}"
                output = self.connect_and_execute(server, command)
                print(f"✓ Deleted source directory: {job_path}\n")
            elif del_dir == 'n':
                print(f"✓ Retained source directory: {job_path}\n")
            else:
                print(f"❌ Invalid choice\n")
                
            return True
        else:
            print(f"✗ Failed to kill job {job_id}\n")
            return False
    
    def view_log(self, job_id_input):
        """View log file for a job (like tail -f)"""
        # Find the job in our list
        matched_job = None
        
        for job in self.all_jobs:
            if job_id_input in job['JobID'] or job['JobID'].startswith(job_id_input + '.'):
                matched_job = job
                break
        
        if not matched_job:
            print(f"\n❌ Job ID '{job_id_input}' not found in current job list")
            print(f"   Please refresh the job list first (option 8)")
            return False
        
        server_hostname = matched_job['Server']
        job_path = matched_job['Job_Path']
        log_file = f"{job_path}/Simulation/messag"
        
        # Find the server config
        server = None
        for s in self.servers:
            if s['name'] == server_hostname:
                server = s
                break
        
        if not server:
            print(f"❌ Server {server_hostname} not found in configuration")
            return False
        
        # Check if log file exists
        check_cmd = f"test -f {log_file} && echo 'EXISTS' || echo 'NOT_FOUND'"
        result = self.connect_and_execute(server, check_cmd)
        
        if not result or 'NOT_FOUND' in result:
            print(f"\n❌ Log file not found: {log_file}")
            return False
        
        print(f"\n📄 Viewing log for job: {matched_job['JobID']}")
        print(f"   Job Name: {matched_job['Job_Name']}")
        print(f"   Server: {server_hostname}")
        print(f"   Log file: {log_file}")
        print(f"\n{'=' * 70}")
        print("Press Ctrl+C to stop watching the log")
        print('=' * 70 + '\n')
        
        # Get initial content (last 50 lines)
        initial_cmd = f"tail -n 50 {log_file}"
        initial_output = self.connect_and_execute(server, initial_cmd)
        
        if initial_output:
            print(initial_output)
        
        # Keep track of file size for detecting new content
        prev_size = 0
        size_cmd = f"stat -c %s {log_file} 2>/dev/null || stat -f %z {log_file}"
        size_result = self.connect_and_execute(server, size_cmd)
        if size_result and size_result.strip().isdigit():
            prev_size = int(size_result.strip())
        
        try:
            while True:
                time.sleep(3)
                
                # Check current file size
                size_result = self.connect_and_execute(server, size_cmd)
                if not size_result or not size_result.strip().isdigit():
                    continue
                
                current_size = int(size_result.strip())
                
                # If file grew, get new content
                if current_size > prev_size:
                    # Get new bytes
                    bytes_to_read = current_size - prev_size
                    new_content_cmd = f"tail -c {bytes_to_read} {log_file}"
                    new_content = self.connect_and_execute(server, new_content_cmd)
                    
                    if new_content:
                        print(new_content, end='', flush=True)
                    
                    prev_size = current_size
                elif current_size < prev_size:
                    # File was truncated or replaced
                    print(f"\n[Log file was reset/truncated]\n")
                    new_content_cmd = f"tail -n 50 {log_file}"
                    new_content = self.connect_and_execute(server, new_content_cmd)
                    if new_content:
                        print(new_content)
                    prev_size = current_size
                
        except KeyboardInterrupt:
            print(f"\n\n{'=' * 70}")
            print("✓ Stopped watching log file")
            print('=' * 70 + '\n')
            return True
    
    def windows_to_linux_path(self, windows_path):
        """Convert Windows path to Linux path and determine server"""
        windows_path = os.path.abspath(windows_path)
        drive = windows_path[0].upper()
        
        if drive not in self.drive_mapping:
            return None, None
        
        server_hostname = self.drive_mapping[drive]
        
        # Remove drive letter and convert to Linux path
        path_after_drive = windows_path[2:].replace('\\', '/')
        linux_path = f"{self.linux_base_path}/{self.user}{path_after_drive}"
        
        return server_hostname, linux_path
    
    def get_drive_letter(self, path):
        """Extract drive letter from path"""
        abs_path = os.path.abspath(path)
        return abs_path[0].upper() if len(abs_path) > 0 else None
    
    def copy_directory_contents(self, source, destination):
        """Copy all contents from source to destination"""
        try:
            if not os.path.exists(destination):
                os.makedirs(destination)
                print(f"✓ Created directory: {destination}")
            
            print(f"📁 Copying files from {source} to {destination}...")
            
            for item in os.listdir(source):
                source_item = os.path.join(source, item)
                dest_item = os.path.join(destination, item)
                
                if os.path.isdir(source_item):
                    shutil.copytree(source_item, dest_item)
                else:
                    shutil.copy2(source_item, dest_item)
            
            print(f"✓ Successfully copied all files\n")
            return True
            
        except Exception as e:
            print(f"❌ Error copying files: {str(e)}\n")
            return False
    
    def submit_job_interactive(self):
        """Interactive job submission with path handling"""
        print("\n" + "=" * 70)
        print("                     Submit New Job")
        print("=" * 70)
        
        # Get current directory
        current_dir = os.getcwd()
        print(f"\n📂 Current directory: {current_dir}")
        
        # Ask user choice
        print("\nWhere do you want to run the job from?")
        print("[1] Current directory")
        print("[2] Custom path")
        
        choice = input("\nEnter choice: ").strip()
        
        server_hostname = None
        job_path = None
        
        if choice == '1':
            # Option i) - Run from current directory
            server_hostname, job_path = self.windows_to_linux_path(current_dir)
            
            if not server_hostname:
                drive_letters = ', '.join(self.drive_mapping.keys())
                print(f"❌ Current directory is not on a mapped drive ({drive_letters})")
                return False
            
            print(f"\n✓ Server: {server_hostname}")
            print(f"✓ Linux path: {job_path}\n")
            
        elif choice == '2':
            # Option ii) - Custom path
            custom_path = input("\nEnter custom path: ").strip()
            
            if not os.path.exists(custom_path):
                print(f"❌ Path does not exist: {custom_path}")
                return False
            
            drive = self.get_drive_letter(custom_path)
            
            if drive in self.drive_mapping:
                # Custom path is on mapped drive
                server_hostname, job_path = self.windows_to_linux_path(custom_path)
                print(f"\n✓ Server: {server_hostname}")
                print(f"✓ Linux path: {job_path}\n")
                
            else:
                # Custom path (HOME) is NOT on mapped drive
                drive_letters = ', '.join(self.drive_mapping.keys())
                print(f"\n⚠️  Path is not on a mapped drive ({drive_letters})")
                print(f"   You need to copy files to a mapped location.\n")
                
                # Ask for server
                print("Available servers:")
                for i, srv in enumerate(self.servers, 1):
                    drive_letter = self.server_to_drive.get(srv['hostname'], '?')
                    print(f"  [{i}] {srv['name']} (Drive {drive_letter}:)")
                
                srv_choice = input("\nSelect server (number): ").strip()
                try:
                    srv_idx = int(srv_choice) - 1
                    if 0 <= srv_idx < len(self.servers):
                        server_hostname = self.servers[srv_idx]['hostname']
                    else:
                        print("❌ Invalid server selection")
                        return False
                except ValueError:
                    print("❌ Invalid input")
                    return False
                
                # Get the corresponding drive letter for the selected server
                required_drive = self.server_to_drive.get(server_hostname)
                if not required_drive:
                    print(f"❌ No drive mapping found for server {server_hostname}")
                    return False
                
                print(f"\n✓ Selected server: {server_hostname}")
                print(f"✓ Destination must be on drive {required_drive}:\n")
                
                while True:
                    dest_path = input(f"Enter destination path (must start with {required_drive}:\\): ").strip()
                    dest_drive = self.get_drive_letter(dest_path)
                    
                    if dest_drive != required_drive:
                        print(f"❌ Destination must be on drive {required_drive}: (selected server: {server_hostname})")
                        continue
                    
                    # Check if destination exists
                    if os.path.exists(dest_path):
                        if os.listdir(dest_path):  # Directory is not empty
                            print(f"\n⚠️  WARNING: Destination directory is not empty!")
                            print(f"   Files in: {dest_path}")
                            action = input("   [1] Enter new path  [2] Continue anyway: ").strip()
                            
                            if action == '1':
                                continue
                            elif action != '2':
                                print("❌ Invalid choice")
                                return False
                        else:
                            print(f"✓ Destination directory exists and is empty")
                    
                    # Copy files
                    if not self.copy_directory_contents(custom_path, dest_path):
                        return False
                    
                    # Extract server and job path from DEST
                    _, job_path = self.windows_to_linux_path(dest_path)
                    print(f"✓ Server: {server_hostname}")
                    print(f"✓ Linux path: {job_path}\n")
                    break
        
        else:
            print("❌ Invalid choice")
            return False
        
        # Now submit the job using the configured submit script name
                                       
        time.sleep(1)
        
        return self.submit_job(server_hostname, job_path, self.submit_script_name)
    
    def submit_job(self, server_hostname, job_path, script_name=None):
        """Submit a job to specified server"""
        # Use configured script name if not provided
        if script_name is None:
            script_name = self.submit_script_name
        
        # Find the server config
        server = None
        for s in self.servers:
            if s['hostname'] == server_hostname:
                server = s
                break
        
        if not server:
            print(f"❌ Server {server_hostname} not found in configuration")
            return False
        
        print(f"\n🚀 Submitting job on {server_hostname}...")
        print(f"   Path: {job_path}")
        print(f"   Script: {script_name}\n")
        
        command = f"cd {job_path} && {self.qsub_path} {script_name}"
        output = self.connect_and_execute(server, command)
        
        if output:
            print(f"✓ Job submitted successfully!")
            print(f"  Output: {output.strip()}\n")
            
            input("Press Enter to refresh job list...")
            self.fetch_all_jobs()
            self.display_jobs()
            
            return True
        else:
            print(f"✗ Job submission failed\n")
            return False


def print_menu():
    """Print the main menu"""
    print("=" * 70)
    print("         PBS PRO Job Monitor & Submitter")
    print("=" * 70)
    print("\n[1] Display All Jobs")
    print("[2] Display Jobs (Sorted)")
    print("[3] Filter Jobs by Status")
    print("[4] Filter Jobs by Owner")
    print("[5] Submit New Job")
    print("[6] Kill Job")
    print("[7] View Job Log (tail -f)")
    print("[8] Refresh Job List")
    print("[0] Exit")
    print("\n" + "=" * 70)


def get_sort_menu():
    """Get sorting preference"""
    print("\nSort by:")
    print("[1] JobID")
    print("[2] Job Name")
    print("[3] CPUs")
    print("[4] Status")
    print("[5] Owner")
    print("[6] Server")
    print("[7] Memory")
    
    choice = input("\nEnter choice: ").strip()
    
    sort_map = {
        '1': 'JobID',
        '2': 'Job_Name',
        '3': 'CPUs',
        '4': 'Status',
        '5': 'Owner',
        '6': 'Server',
        '7': 'Memory'
    }
    
    return sort_map.get(choice, 'JobID')


def main():
    # Parse command line arguments for config file
    config_path = None
    if len(sys.argv) > 1:
        if sys.argv[1] in ['-c', '--config']:
            if len(sys.argv) > 2:
                config_path = sys.argv[2]
            else:
                print("❌ Error: --config requires a path argument")
                sys.exit(1)
        elif sys.argv[1] in ['-h', '--help']:
            print("Usage: pbs_monitor.py [-c CONFIG_PATH]")
            print("\nOptions:")
            print("  -c, --config PATH   Path to configuration YAML file")
            print("  -h, --help          Show this help message")
            sys.exit(0)
    
    # Load configuration
    print("\n" + "=" * 70)
    print("         PBS PRO Job Monitor - Startup")
    print("=" * 70 + "\n")
    
    config = load_config(config_path)
    validate_config(config)
    
    # Get current Windows username
    windows_username = getuser()
    
    print(f"\n👤 Detected Windows user: {windows_username}")
    print(f"   This will be used for SSH connections to all servers.\n")
    
    # Initialize manager with config
    manager = PBSJobManager(config, windows_username)
    
    print(f"\n📂 Remote script path: {manager.script_path}")
    print(f"📁 Linux base path: {manager.linux_base_path}")
    print(f"📜 PBS submit script: {manager.submit_script_name}")
    
    # Display configured servers
    print(f"\n🖥️  Configured servers:")
    for srv in manager.servers:
        drive = manager.server_to_drive.get(srv['hostname'], '?')
        print(f"   - {srv['name']} ({srv['hostname']}) -> Drive {drive}:")
    
    # Initial fetch
    manager.fetch_all_jobs()
    
    while True:
        print_menu()
        choice = input("Enter your choice: ").strip()
        
        if choice == '0':
            print("\n👋 Goodbye!\n")
            break
            
        elif choice == '1':
            manager.display_jobs()
            
        elif choice == '2':
            sort_by = get_sort_menu()
            manager.display_jobs(sort_by=sort_by)
            
        elif choice == '3':
            status = input("\nEnter status (R/Q): ").strip().upper()
            filtered = [j for j in manager.all_jobs if j['Status'] == status]
            print(f"\n📋 Jobs with status '{status}':\n")
            manager.display_jobs(filtered)
            
        elif choice == '4':
            owner = input("\nEnter owner username: ").strip()
            filtered = [j for j in manager.all_jobs if j['Owner'] == owner]
            print(f"\n📋 Jobs owned by '{owner}':\n")
            manager.display_jobs(filtered)
            
        elif choice == '5':
            manager.submit_job_interactive()
            
        elif choice == '6':
            print("\n" + "=" * 70)
            print("                     Kill Job")
            print("=" * 70)
            
            job_id = input("\nEnter Job ID (or partial ID): ").strip()
            
            if manager.kill_job(job_id):
                input("\nPress Enter to refresh job list...")
                manager.fetch_all_jobs()
                manager.display_jobs()
        
        elif choice == '7':
            manager.display_jobs()
            print("\n" + "=" * 70)
            print("                     View Job Log")
            print("=" * 70)
            
            job_id = input("\nEnter Job ID (or partial ID): ").strip()
            manager.view_log(job_id)
                
        elif choice == '8':
            manager.fetch_all_jobs()
            manager.display_jobs()
            
        else:
            print("\n❌ Invalid choice. Please try again.\n")
        
        input("\nPress Enter to continue...")
        print("\n" * 2)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Interrupted by user. Goodbye!\n")
        sys.exit(0)