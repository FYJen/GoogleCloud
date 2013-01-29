#!/bin/bash

gcutil addinstance --image=projects/google/images/ubuntu-10-04-v20120912 $1 --wait_until_running --machine_type=n1-standard-4-d --zone=us-east1-a
