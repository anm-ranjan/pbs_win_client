# Configuration Guide

This document provides detailed information about configuring the PBS Job Monitor.

## Quick Start

1. Copy `config.yaml.example` to `config.yaml`
2. Update server IP addresses
3. Update drive mappings
4. Verify PBS paths

## Configuration Sections

### PBS Paths


pbs:
  qdel_path: "/opt/pbs/bin/qdel"
  qsub_path: "/opt/pbs/bin/qsub"
  submit_script_name: "qsub.sh"
  
To find the correct paths on your Linux servers:

ssh user@server "which qsub"
ssh user@server "which qdel"

Common locations:

/opt/pbs/bin/ (PBS Pro default)
/usr/bin/ (system-wide installation)
/opt/pbspro/bin/ (alternative installation)

Linux Paths
paths:
  linux_base_path: "/mnt/fhgfs"
  remote_script_name: "que.py"
  
The linux_base_path is the mount point of your shared filesystem. Common examples:

/mnt/fhgfs (BeeGFS/FHGFS)
/home (NFS home directories)
/scratch (Scratch filesystem)
/gpfs (IBM Spectrum Scale)

Drive Mapping
drive_mapping:
  X: "192.168.1.10"
  Y: "192.168.1.11"
  Z: "192.168.1.12"
  
How to determine your mappings:

Open Windows Explorer
Note which drive letters are mapped to network locations
Identify which Linux server serves each drive
Match the drive letter to the server IP
Important: The server in drive_mapping must also appear in the servers list.

Server List
servers:

  - hostname: "192.168.1.10"

    name: "Production-HPC"

  
  - hostname: "192.168.1.11"  

    name: "Development-HPC"
    
hostname: The actual IP or DNS name used for SSH connections
name: A friendly name displayed in the application

SSH Settings
ssh:
  connection_timeout: 10
  ### key_file: "/path/to/custom/key"
Default SSH key locations checked:

Custom path specified in key_file
~/.ssh/id_rsa (Windows: C:\Users\username\.ssh\id_rsa)
Multiple Configurations
You can maintain multiple configuration files for different environments:

### Production

python pbs_monitor.py -c configs/production.yaml

### Development  

python pbs_monitor.py -c configs/development.yaml

### Testing

python pbs_monitor.py -c configs/test.yaml
Validation
The application validates configuration on startup. Common errors:

Error	Cause	Fix
Missing section: 'pbs'	YAML section not found	Add the pbs: section
Missing key: 'pbs.qdel_path'	Required key missing	Add qdel_path under pbs
'servers' must be a list	Wrong YAML format	Use - hostname: list format
'drive_mapping' cannot be empty	No drives configured	Add at least one drive mapping

Example Configurations
Minimal Configuration
pbs:
  qdel_path: "/opt/pbs/bin/qdel"
  qsub_path: "/opt/pbs/bin/qsub"

paths:
  linux_base_path: "/mnt/fhgfs"
  remote_script_name: "que.py"

drive_mapping:
  X: "192.168.1.10"

servers:

  - hostname: "192.168.1.10"

    name: "Server1"
    
Multi-Cluster Configuration
pbs:
  qdel_path: "/opt/pbs/bin/qdel"
  qsub_path: "/opt/pbs/bin/qsub"

paths:
  linux_base_path: "/mnt/shared"
  remote_script_name: "que.py"

drive_mapping:
  P: "10.0.1.100"
  Q: "10.0.1.101"
  R: "10.0.1.102"
  S: "10.0.2.100"
  T: "10.0.2.101"

servers:
  ### Cluster A

  - hostname: "10.0.1.100"

    name: "ClusterA-Node1"

  - hostname: "10.0.1.101"

    name: "ClusterA-Node2"

  - hostname: "10.0.1.102"

    name: "ClusterA-Node3"
  
  ### Cluster B

  - hostname: "10.0.2.100"

    name: "ClusterB-Node1"

  - hostname: "10.0.2.101"

    name: "ClusterB-Node2"

ssh:
  connection_timeout: 15