#!/bin/bash

host_name=`hostname`


#for size in 1024000 10240000 52100000 102400000
for size in 102400 102401 102402 102403
do
    echo -e "\nCreating dummy files ..."
    echo -e "================================================"
    dd if=/dev/zero of=output.dat  bs=1024  count=$size
    echo -e "A $size size of file has been generated ..."
    echo -e "Start pushing and pulling files ...\n\n"
    for o_host in ajen1001 ajen1002
    do 
        for num_time in 1 2 3
        do 
            echo -e "######################### ____$num_time START ____##########################\n"
            echo -e "Internal - $host_name to $o_host : Push case ..."
            echo -e "================================================"    
            date
            time scp output.dat FJen@$o_host:.
            echo -e "Done ...\n\n"
            echo -e "Internal - $host_name to $o_host : Pull case ..."
            echo -e "================================================"    
            date
            time scp FJen@$o_host:output.dat .
            echo -e "Done ...\n"
            echo -e "######################### ____ $num_time END ____##########################\n"
        done
    done
    rm output.dat
done

echo -e ""
echo "All the internal tests have been done ...."