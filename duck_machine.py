"""
Duck Machine model DM2022W, 
a simulated computer. 

Interprets Duck Machine object code. 
"""

from memory import Memory, MemoryMappedIO
from cpu import CPU

import view

import argparse
import sys
import io

from typing import List, Tuple

import logging
logging.basicConfig()
log = logging.getLogger(__name__)
log.setLevel(logging.INFO)


def cli() -> object:
    """Get arguments from command line"""
    parser = argparse.ArgumentParser(description="Duck Machine Simulator")
    parser.add_argument("objfile", type=argparse.FileType('r'),
                            help="Object file input")
    parser.add_argument("-d", "--display", help="Graphical display",
                        action="store_true")
    parser.add_argument("-s", "--step", help="Single step mode",
                        action="store_true")
    args = parser.parse_args()
    return args

def load(file: io.IOBase, memory: Memory) -> None:
    addr = 0
    for line in file:
        word = int(line)
        memory.put(addr, word)
        addr += 1

def duck_out(addr: int, value: int) -> None:
    print("Quack!: {}".format(value))

def duck_in(addr: int) -> int:
    return int(input("Quack! Gimme an int! "))

def main():
    """" Run a Duck Machine program from
    object code file.
    """
    args = cli()
    mem = MemoryMappedIO(512)
    # We'd like to make it simple to trigger I/O with
    # a single instruction, so it would be good to fit
    # the memory mapped addresses into the offset field.
    # For that, maximum positive value is 511.  We'll
    # reserve addresses 510 and 511 for input and output
    # respectively.
    mem.map_address_in(510,duck_in)
    mem.map_address_out(511,duck_out)
    cpu = CPU(mem)
    if args.display: 
       display = view.MachineStateView(cpu,1200,800)
    load(args.objfile, mem)
    cpu.run(single_step=args.step)
    print("Halted")
    if args.display:
      input("Press enter to end")


if __name__ == "__main__":
    main()
