#!/bin/bash

for i in `seq 1 1000`; 
do 
	qsub -cwd -N test.$i -b y "echo `hostname`" ; 
done
