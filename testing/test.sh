#!/bin/bash

# must run this from home dir 
cd ~

for i in `seq 1 1000`;
do
        qsub -cwd -N test.$i -b y "echo `hostname`";
done
