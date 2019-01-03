#!/env/usr/python

import sys
import argparse
import os
import numpy as np
import pandas as pd
import tejas
from pandas import DataFrame
from pandas import MultiIndex
# usage:

#def readable_dir(prospective_dir):
#  if not os.path.isdir(prospective_dir):
#    raise Exception("readable_dir:{0} is not a valid path".format(prospective_dir))
#  if os.access(prospective_dir, os.R_OK):
#    return prospective_dir
#  else:
#    raise Exception("readable_dir:{0} is not a readable dir".format(prospective_dir))
#
#parser = argparse.ArgumentParser(description='Process output files')
#parser.add_argument('bench', metavar='B', type=str, nargs='+',
#                    help='an integer for the accumulator')
#parser.add_argument('-p','--path',type=readable_dir)
#
#args = parser.parse_args()

cores = range(1)

halted_tiles = [4,8,27,30,33,37]
map_core_to_tile = list(filter(lambda a: a not in halted_tiles,[i for i in range(38) for _ in range(2)]))
 
# parse KNL output
papi_counters = ['cycles','inst','l1accesses','l1misses','l2accesses','l2misses','l2hits','instl2miss','mcdram',\
                 'mcdramfar','mcdramnear','l2tlbmisses','l1tlbmisses']

parallel = False

if "poly"==sys.argv[1]:
    #sizes = ['MINI', 'SMALL', 'MEDIUM', 'LARGE', 'EXTRALARGE']
    sizes = ['MINI','SMALL','MEDIUM']
    benchmarks = ['correlation','covariance','gemm','gemver','gesummv','symm','syr2k','syrk','trmm',\
                  '2mm','3mm','atax','bicg','doitgen','mvt','cholesky','durbin','gramschmidt',\
                  'lu','ludcmp','trisolv','adi','jacobi-1d','jacobi-2d','heat-3d','fdtd-2d','seidel-2d']
    idx = MultiIndex.from_product([benchmarks,sizes])
elif "parboil"==sys.argv[1]:
    parallel = True
    #sizes = ['UT','small','default','short','medium','medium','small','small']
    #benchmarks = ['bfs','cutcp','histo','lbm','sgemm','spmv','stencil','tpacf']
    sizes = ['medium']
    benchmarks = ['spmv']
    cores = range(64)
    idx = MultiIndex.from_arrays([benchmarks*len(cores),sizes*len(cores),list(cores)*len(benchmarks)])
else:
    print("Benchmark not known!")
    exit(0)

knl_df = pd.DataFrame(0,columns=papi_counters,index=idx)
tejas_df = pd.DataFrame(0,columns=papi_counters,index=idx)

list_df = {}
path = "./outputs/"

affinity = [0,1,20,21,22,23,52,53,\
            28,29,50,51,2,3,30,31,\
            36,37,56,57,8,9,38,39,\
            44,45,62,63,14,15,46,47,\
            4,5,24,25,48,49,6,7,26,27,\
            10,11,32,33,12,13,34,35,54,55,\
            16,17,40,41,58,59,18,19,42,43,60,61]

for b in benchmarks:
    for s in sizes:
        print("parsing " + b + " for size " + s + " (" + str(len(cores)) + " core/s) ...")
        tejas_file = path + "knl-" + b + "-" + str(s) + ".output"
        core,tile=tejas.parse(tejas_file)
        knl_file = path + b + "-" + s + ".output"
        f = open(knl_file)
        c = 0
        for l in f:
            if len(l.strip().split(" "))<=1: continue
            # format splited only by spaces
            if len(l.strip().split(" "))==len(papi_counters):
                knl_df.loc[b,s] = [int(i) for i in l.strip().split(" ")]
            else:
                # format -> PAPI thread X\tCOUNTER1 COUNTER2 ... COUNTERN
                if len(l.strip().split("\t"))<=1: continue
                knl_df.loc[b,s,affinity[c]] = [int(i) for i in l.strip().split("\t")[1].split(" ")]
                c += 1
        for core_monitor in cores:
            print("\tcore " + str(core_monitor+1) + "/" + str(len(cores)) +\
                   " (tile " + str(map_core_to_tile[core_monitor]) + ") ...")
            list_df[b]= {'core':core,'tile':tile}
            
            if len(cores)>1:
                i = (b,s,core_monitor)
            else:
                i = (b,s)
            tejas_df.loc[i].cycles = core['timing'].cycles[core_monitor]
            tejas_df.loc[i].inst = core['timing'].instructions[core_monitor]
            #tejas_df.loc[i].inst = core['timing'].ciscinst[core_monitor]
            #tejas_df.loc[i].l1accesses = core['memory'].l1.data.hits[core_monitor] + core['memory'].l1.data.misses[core_monitor]
            tejas_df.loc[i].l1accesses = core['memory'].l1.data.acc[core_monitor]
            tejas_df.loc[i].l1misses = core['memory'].l1.data.misses[core_monitor]
            tile_monitor = map_core_to_tile[core_monitor]
            tejas_df.loc[i].l2hits = tile['memory'].l2.hits[tile_monitor]
            tejas_df.loc[i].l2accesses = tile['memory'].l2.hits[tile_monitor] + tile['memory'].l2.misses[tile_monitor]
            tejas_df.loc[i].l2misses = tile['memory'].l2.misses[tile_monitor]
            tejas_df.loc[i].instl2miss = tile['memory'].l2.misses[tile_monitor]
            if parallel:
                tejas_df.loc[i].l2hits /= 2
                tejas_df.loc[i].l2accesses /= 2
                tejas_df.loc[i].l2misses /= 2
                tejas_df.loc[i].instl2miss /= 2
            for r in range(2,8):
                tejas_df.loc[i].mcdramfar += core['memory'].main.mcdram[r][core_monitor]
            for r in range(0,2):
                tejas_df.loc[i].mcdramnear += core['memory'].main.mcdram[r][core_monitor]
            tejas_df.loc[i].mcdram = tejas_df.loc[i].mcdramfar + tejas_df.loc[i].mcdramnear
            tejas_df.loc[i].l1tlbmisses = core['memory'].tlb.data.misses[core_monitor]
            tejas_df.loc[i].l2tlbmisses = core['memory'].tlb.data.hits[core_monitor] + core['memory'].tlb.data.misses[core_monitor]
        

#print("Absolute error in terms of cycles:")
#for b in benchmarks:
#    print(b + "\t\t" + str(abs((knl_df.cycles[b]-list_df[b]['core']['timing'].cycles[0])/knl_df.cycles[b])))
    
#print("Absolute error in terms of cache accesses misses:")
#for b in benchmarks:
#    m = list_df[b]['core']['memory']
#    l1acc = abs((knl_df.l1accesses[b]-(m.l1.data.hits[0]+m.l1.data.misses[0])/knl_df.l1accesses[b]))
#    print(b + "\t\t" + str(l1acc))
