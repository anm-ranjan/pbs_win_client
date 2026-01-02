# PBS PRO Job Monitor & Submitter

A Windows CLI tool to monitor, submit, and manage LS-DYNA simulation jobs running on PBS PRO across multiple Linux servers via SSH.

![Python Version](https://img.shields.io/badge/python-3.7%2B-blue)
![Platform](https://img.shields.io/badge/platform-Windows-lightgrey)
![License](https://img.shields.io/badge/license-MIT-green)

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
  - [Configuration File Location](#configuration-file-location)
  - [Configuration Parameters](#configuration-parameters)
  - [Server Setup](#server-setup)
  - [Drive Mapping](#drive-mapping)
- [Usage](#usage)
  - [Starting the Application](#starting-the-application)
  - [Menu Options](#menu-options)
  - [Submitting Jobs](#submitting-jobs)
  - [Viewing Logs](#viewing-logs)
- [Assumptions](#assumptions)
- [File Structure on Linux Servers](#file-structure-on-linux-servers)
- [Limitations](#limitations)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [License](#license)

---

## Overview

This tool provides a unified interface for engineers to:
- Monitor PBS PRO job queues across multiple HPC Linux servers from a Windows workstation
- Submit new LS-DYNA simulation jobs
- Kill running or queued jobs
- View real-time simulation logs (similar to `tail -f`)
- Manage job directories

The tool uses SSH (via Paramiko) to connect to Linux servers and execute PBS commands remotely. It assumes that the PBS job is executed via a run script that generates a folder named 'Simulation' in the current directory of the compute node.

---

## Features

| Feature | Description |
|---------|-------------|
| **Multi-Server Monitoring** | Connect to multiple Linux HPC servers simultaneously |
| **Job Queue Display** | View all jobs with details (ID, name, CPUs, status, owner, memory) |
| **Sorting & Filtering** | Sort by any column; filter by status (R/Q) or owner |
| **Job Submission** | Submit jobs from Windows with automatic path conversion |
| **File Copying** | Copy job files from local drives to mapped network drives |
| **Job Termination** | Kill jobs with optional directory cleanup |
| **Live Log Viewing** | Real-time log monitoring (like `tail -f`) |
| **SSH Key Authentication** | Supports both SSH key and password authentication |
| **YAML Configuration** | All settings externalized to a configuration file |

---

## Prerequisites

### Windows Workstation
- Python 3.7 or higher
- Network access to Linux servers (SSH port 22)
- Mapped network drives to Linux filesystem (e.g., X:, Y:, Z:)

### Linux Servers
- PBS PRO scheduler installed and configured
- Python 3.x installed
- `que.py` script deployed (companion script for job listing)
- `qsub.py` script in simulation directory for submitting PBS job
- SSH server running
- User accounts with SSH access

### Network Requirements
- SSH connectivity from Windows to all Linux servers
- Network drives mapped to the shared filesystem

---

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/anm-ranjan/pbs_win_client
cd pbs_win_client
```

### 2. Create Virtual Environment (Recommended)

```bash
python -m venv venv
```

**Activate virtual environment:**

On Windows (Command Prompt):
```cmd
venv\Scripts\activate.bat
```

On Windows (PowerShell):
```powershell
venv\Scripts\Activate.ps1
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Create Configuration File

```bash
# Copy the example configuration
copy config.yaml.example config.yaml

# Edit with your settings
notepad config.yaml
```

### 5. Setup SSH Keys (Recommended)

```bash
# Generate SSH key pair if you don't have one
ssh-keygen -t rsa -b 4096

# Copy public key to each Linux server
# You'll need to do this manually or use ssh-copy-id from Git Bash
```

---

## Configuration

### Configuration File Location

The application searches for `config.yaml` in the following order:

1. Path specified via command line (`-c` or `--config`)
2. Current working directory (`./config.yaml`)
3. User's home directory (`~/.pbs_monitor/config.yaml`)
4. Same directory as the script (`/config.yaml`)

### Configuration Parameters

```yaml
# config.yaml - Full Configuration Reference

# ============================================================================
# PBS PRO COMMAND PATHS
# ============================================================================
# Absolute paths to PBS PRO commands on the Linux servers
# These must match the actual installation paths on your HPC systems

pbs:
  qdel_path: "/opt/pbs/bin/qdel"    # Path to job deletion command
  qsub_path: "/opt/pbs/bin/qsub"    # Path to job submission command
  submit_script_name: "qsub.sh"     # Run script for executing PBS PRO job

# ============================================================================
# FILESYSTEM PATHS
# ============================================================================

paths:
  # Base path for user directories on the Linux filesystem
  # The tool will append /{username} to this path
  # Example: /mnt/dir + /john.doe = /mnt/dir/john.doe
  linux_base_path: "/mnt/dir"
  
  # Name of the remote Python script that queries PBS job information
  # This script must exist at: {linux_base_path}/{username}/{remote_script_name}
  remote_script_name: "que.py"

# ============================================================================
# DRIVE MAPPING
# ============================================================================
# Maps Windows drive letters to Linux server hostnames/IPs
# This determines which server handles jobs from which drive
# 
# Format:
# DRIVE_LETTER: "server_hostname_or_ip"
# 
# The Windows path X:\project\simulation becomes:
# /mnt/dir/{username}/project/simulation on server 192.168.1.10

drive_mapping:
  X: "192.168.1.10"   # Server 1
  Y: "192.168.1.11"   # Server 2  
  Z: "192.168.1.12"   # Server 3

# ============================================================================
# SERVER CONFIGURATIONS
# ============================================================================
# List of all Linux servers to monitor
# Each server requires:
# - hostname: IP address or DNS hostname (must be reachable via SSH)
# - name: Display name shown in the UI (can be any friendly name)
# 
# Note: 'username' and 'key_file' are automatically populated at runtime
# based on the current Windows user

servers:
  - hostname: "192.168.1.10"
    name: "HPC-Node-01"
  
  - hostname: "192.168.1.11"
    name: "HPC-Node-02"
  
  - hostname: "192.168.1.12"
    name: "HPC-Node-03"

# ============================================================================
# SSH CONFIGURATION (Optional)
# ============================================================================

ssh:
  # Connection timeout in seconds
  connection_timeout: 10
  
  # SSH private key file path (optional)
  # Leave empty or remove to auto-detect from ~/.ssh/id_rsa
  # key_file: "C:/Users/username/.ssh/custom_key"
```

### Server Setup

Each Linux server must have:

- PBS PRO installed at the configured paths
- User home directory at `{linux_base_path}/{username}/`
- `que.py` script at `{linux_base_path}/{username}/que.py`
- `qsub.py` script in simulation directory for submitting PBS job
- SSH access enabled for the Windows user

### Drive Mapping

The drive mapping connects Windows network drives to Linux servers:

| Windows Drive | Linux Server | Linux Path |
|---------------|--------------|------------|
| `X:\project\sim1` | 192.168.1.10 | `/mnt/dir/username/project/sim1` |
| `Y:\jobs\test` | 192.168.1.11 | `/mnt/dir/username/jobs/test` |
| `Z:\archive\old` | 192.168.1.12 | `/mnt/dir/username/archive/old` |

**Important:** Ensure your Windows network drives are correctly mapped (samba) to the shared filesystem accessible by the Linux servers.

---

## Usage

### Starting the Application

```bash
# Basic usage (uses default config locations)
python pbs_monitor.py

# Specify custom config file
python pbs_monitor.py -c /path/to/config.yaml
python pbs_monitor.py --config C:\configs\production.yaml

# Show help
python pbs_monitor.py --help
```

### Menu Options

```
PBS PRO Job Monitor & Submitter
======================================================================
[1] Display All Jobs           - Show all jobs from all servers
[2] Display Jobs (Sorted)      - Sort by JobID, Name, CPUs, Status, etc.
[3] Filter Jobs by Status      - Filter by R (Running) or Q (Queued)
[4] Filter Jobs by Owner       - Filter by username
[5] Submit New Job             - Interactive job submission
[6] Kill Job                   - Terminate a job (with optional cleanup)
[7] View Job Log (tail -f)     - Real-time log monitoring
[8] Refresh Job List           - Re-fetch jobs from all servers
[0] Exit                       - Exit the application
======================================================================
```

### Submitting Jobs

When submitting a job, you have two options:

#### Option 1: Submit from Current Directory

```
📂 Current directory: X:\projects\crash_simulation

Where do you want to run the job from?
[1] Current directory
[2] Custom path

Enter choice: 1

✓ Server: 192.168.1.10
✓ Linux path: /mnt/dir/john.doe/projects/crash_simulation
```

#### Option 2: Submit from Custom Path

If the path is on a mapped drive:

```
Enter custom path: Y:\simulations\model_v2

✓ Server: 192.168.1.11
✓ Linux path: /mnt/dir/john.doe/simulations/model_v2
```

If the path is NOT on a mapped drive (e.g., local C: drive):

```
Enter custom path: C:\Users\john\Desktop\new_model

⚠️ Path is not on a mapped drive (X, Y, Z)
You need to copy files to a mapped location.

Available servers:
[1] HPC-Node-01 (Drive X:)
[2] HPC-Node-02 (Drive Y:)
[3] HPC-Node-03 (Drive Z:)

Select server (number): 1

Enter destination path (must start with X:): X:\projects\new_model

📁 Copying files from C:\Users\john\Desktop\new_model to X:\projects\new_model...
✓ Successfully copied all files
```

### Viewing Logs

The log viewer works like `tail -f`, showing real-time updates:

```
📄 Viewing log for job: 12345.server1
Job Name: crash_sim_v3
Server: HPC-Node-01
Log file: /mnt/dir/john.doe/project/Simulation/messag

======================================================================
Press Ctrl+C to stop watching the log
======================================================================

cycle    time          dt        response
1        0.000E+00     1.00E-06  0.00E+00
2        1.000E-06     1.00E-06  1.23E-02
3        2.000E-06     1.00E-06  2.45E-02
...
```

Press `Ctrl+C` to stop watching and return to the menu.

---

## Assumptions

### Directory Structure

The tool assumes a specific directory structure for LS-DYNA jobs:

```
job_directory/
├── qsub.sh                # PBS submission script
├── input.k                # LS-DYNA input file
├── Simulation/            # Output directory (created by solver)
│   ├── messag             # LS-DYNA message/log file
│   ├── d3plot             # Results files
│   └── ...
└── other_files/
```

### PBS Submission Script

Jobs are submitted using a script named `qsub.sh` located in the job directory.

### Log File Location

The log viewer looks for the file at:
```
{job_path}/Simulation/messag
```

### User Directory Pattern

User directories follow the pattern:
```
{linux_base_path}/{windows_username}/
```

For example: `/mnt/dir/john.doe/`

### Username Matching

The Windows username is used directly for:
- SSH connections to Linux servers
- Constructing Linux paths

Ensure your Windows username matches your Linux username.

---

## File Structure on Linux Servers

### Required Files

Each Linux server needs the companion script `que.py`:

```
/mnt/dir/{username}/
└── que.py    # Job query script (must output JSON with --json flag)
```

### que.py Output Format

The `que.py` script must output JSON in the following format when called with `--json`:

```json
[
  {
    "JobID": "12345.server1",
    "Job_Name": "crash_simulation",
    "Job_Path": "/mnt/dir/john.doe/project",
    "CPUs": 64,
    "Status": "R",
    "Owner": "john.doe",
    "Memory": "128gb"
  }
]
```

---

## Limitations

| Limitation | Description |
|------------|-------------|
| **Windows Only** | Designed for Windows workstations (path conversion logic) |
| **Same Username** | Windows and Linux usernames must match |
| **Fixed Log Path** | Log file must be at `{job_path}/Simulation/messag` |
| **Network Drives Required** | Job submission requires mapped network drives |
| **No Password Prompt** | Uses SSH keys; no interactive password support |
| **Single User** | Monitors jobs for the current user only (can filter by owner) |
| **PBS PRO Only** | Does not support other schedulers (SLURM, SGE, etc.) |
| **No Job Modification** | Cannot modify running jobs (only kill) |
| **Polling-Based Logs** | Log viewing polls every 3 seconds (not true streaming) |

---

## Troubleshooting

### Connection Errors

**Problem:** `Connection error to server: Authentication failed`

**Solutions:**
- Verify SSH key is in `~/.ssh/id_rsa`
- Ensure public key is in server's `~/.ssh/authorized_keys`
- Check username matches between Windows and Linux
- Test SSH manually: `ssh username@server`

**Problem:** `Connection error to server: timed out`

**Solutions:**
- Verify server IP/hostname is correct
- Check network connectivity: `ping server_ip`
- Verify SSH port (22) is not blocked by firewall
- Increase timeout in config: `ssh.connection_timeout: 30`

### Path Conversion Errors

**Problem:** `Current directory is not on a mapped drive (X, Y, Z)`

**Solutions:**
- Navigate to a mapped drive before running
- Use option [2] Custom path and specify a mapped drive location
- Verify drive mapping in `config.yaml` matches your network drives

**Problem:** Job submitted but not found on server

**Solutions:**
- Verify `linux_base_path` is correct in config
- Check drive mapping matches actual server assignments
- Verify the path exists on the Linux server

### Job Monitoring Issues

**Problem:** `Error parsing JSON from server`

**Solutions:**
- Verify `que.py` exists at the configured path on the server
- Test manually: `ssh user@server "python3 /path/to/que.py --json"`
- Check `que.py` outputs valid JSON format

**Problem:** Jobs not showing up after refresh

**Solutions:**
- Verify PBS PRO is running on the servers
- Check `qstat` works manually on the server
- Ensure `que.py` has correct permissions

### Log Viewing Issues

**Problem:** Log file not found

**Solutions:**
- Verify job has started (status = R)
- Check the job creates output in `Simulation/messag`
- Wait for solver to initialize and create the log file

### Common Configuration Mistakes

| Mistake | Fix |
|---------|-----|
| Wrong PBS paths | SSH to server and run `which qsub` to find correct path |
| IP vs Hostname | Use IP addresses if DNS is unreliable |
| Drive letter case | Use uppercase drive letters (X, not x) |
| Path separators | Use forward slashes in Linux paths |
| Missing trailing slash | `linux_base_path` should NOT have trailing slash |

### Environment Variables

The tool respects the following environment variables:

| Variable | Description |
|----------|-------------|
| `PBS_MONITOR_CONFIG` | Alternative way to specify config file path |
| `HOME` / `USERPROFILE` | Used to locate SSH keys |

---

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Development Setup

```bash
# Clone your fork
git clone https://github.com/anm-ranjan/pbs_win_client
cd pbs_win_client

# Create virtual environment
python -m venv venv
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Make your changes and test
python pbs_monitor.py -c config.yaml.example
```

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## Acknowledgments

- [Paramiko](https://www.paramiko.org/) - SSH library for Python
- [PyYAML](https://pyyaml.org/) - YAML parser for Python
- [PBS PRO](https://www.altair.com/pbs-professional/) - Workload manager
- [que] (https://github.com/jlboat/que) - JSON Export for PBS PRO jobs summary

---

## Support

For issues and feature requests, please use the [GitHub Issues](https://github.com/anm-ranjan/pbs_win_client/issues) page.