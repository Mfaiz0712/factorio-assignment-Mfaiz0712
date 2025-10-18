#!/usr/bin/env python3
"""Toy belt generator."""
import json, random, sys

def main(n_nodes=8):
    nodes = [f"n{i}" for i in range(n_nodes)]
    edges=[]
    sources={}
    sink=nodes[-1]
    for i in range(n_nodes-1):
        lo = random.randint(0,50)
        hi = lo+random.randint(10,60)
        edges.append({"from":nodes[i],"to":nodes[i+1],"lo":lo,"hi":hi})
    sources[nodes[0]]= sum(e["lo"] for e in edges[:3])
    print(json.dumps({"edges":edges,"sources":sources,"sink":sink,"caps":{}}, indent=2))

if __name__=="__main__":
    main()
