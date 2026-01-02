#!/bin/sh
#
#This is an example script for job submission
#
#These commands set up the Grid Environment for your job:
#PBS -N Test
#PBS -l nodes=1,walltime=500:00:00
#PBS -q queueName
#PBS -l ncpus=4
#PBS -o job_log
#PBS -e job_error
#PBS -V


cd $PBS_O_WORKDIR
# lsdyna-Executable
lsdyna=path_to_LSDYNA_exec

###################### License Configurations ######################
export LSTC_LICENSE=network
export LSTC_LICENSE_SERVER=server
export OMP_NUM_THREADS=4
export LSTC_INTERNAL_CLIENT=off

######################    Parameters    #########################
startmodel="test.key" 
jobname="Test"
start_path=`pwd`
NCPU=4
MEM=25M

###################### Execution  ######################
mkdir -p ${start_path}/Simulation
cd ${start_path}/Simulation

cp $start_path/$startmodel  $startmodel

$lsdyna i=${startmodel} ncpu=${NCPU} memory=${MEM}
cd ${start_path}
