# Building the Virtual Duck Machine CPU

In this project we will construct the simulated CPU of
the Duck Machine 2022W, which is identical to
the Duck Machine model 2019W but comes in new
colors and is more expensive.  (Some documentation refers
to earlier models.)
`duck_machine.md` describes
the processor. We will build two files:

* ``instr_format.py`` will contain definitions of the fields
  in the DM2022W instruction word, and a class Instruction to hold
  a "decoded" instruction.  An `Instruction` object will simply
  have a separate field (instance variable) for each of the fields
  in a DM2022W instruction word, plus methods to convert between
  words (integers) and `Instruction` objects.
* ``cpu.py`` will be the central processing unit of the
  DM2022W.  It will define an `ALU` class for the arithmetic and logic unit,
  and a CPU class for the processor of which the ALU is one part.

## Other parts

Some other parts of the Duck Machine are provided for you.

* ``memory.py`` defines the `Memory` class (which is essentially an
  array of integers, like a Python list), and `MemoryMappedIO`.
  `MemoryMappedIO` is like a normal Memory (in fact it is a
  subclass of `Memory`), except it interprets
  some particular addresses as commands for input or output.  As
  the Wikipedia article on memory-mapped IO explains, "One merit
  of memory-mapped I/O is that, by discarding the extra complexity
  that port I/O brings, a CPU requires less internal logic and is
  thus cheaper, faster, easier to build, consumes less power and
  can be physically smaller."  The "easier to build" part is the
  key reason the DM2022W uses memory-mapped IO.
* ``duck_machine.py`` is where we wire together the
  CPU and memory and a graphical display.

 In addition, we will need ``bitfield.py`` from Lab 7.
 Copy it into this project so that we can use it for decoding
 instructions.

## Instruction format

 The format of a Duck Machine instruction word is described
 in ``duck_machine.md``.  Our CPU will need to extract
 and interpret each of those fields.  We will keep the
 relevant definitions in ``instr_format.py``

```python
"""
Instruction format for the Duck Machine 2022W (DM2022W),
a simulated computer modeled loosely on the ARM processor
found in many cell phones and the Raspberry Pi.

Instruction words are unsigned 32-bit integers
with the following fields (from high-order to low-order bits).  
All are unsigned except offset, which is a signed value in 
range -2^11 to 2^11 - 1. 

See docs/duck_machine.md for details. 
"""
```

We will need the `BitField` class from Lab 7 to extract
the parts of an instruction word:

```python
from bitfield import BitField
```

It is convenient to give names to the operation codes of the
DM2022W using a Python *enum*.  For the condition codes,
a special kind of *enum* called a *Flag* is useful, as we'll
discuss below:

```python
from enum import Enum, Flag
```

Defining the layout of the DM2022W instruction word is simple;
we just define a BitField object for each field:

```python
# The field bit positions
reserved = BitField(31,31)
instr_field = BitField(26, 30)
cond_field = BitField(22, 25)
reg_target_field = BitField(18, 21)
reg_src1_field = BitField(14, 17)
reg_src2_field = BitField(10, 13)
offset_field = BitField(0, 9)
```

We won't actually use the `reserved` field, but have given
it a definition just for documentation.  All of the other
fields will be treated as unsigned integers (non-negative values
only), except the `offset` field is signed (**IMPORTANT**: 
remember that the offset can be negative, you will need to use that
knowledge later).
The `cond` (condition code)
field will actually be treated as a small array of bits.

### Operation Codes

The DM2022W has a very small number of operation codes.
It is an extreme example of the *reduced instruction set
computing* (RISC) paradigm, of which the ARM chips are more
typical examples.  You probably have a RISC chip in your phone.
*Complex instruction set computing* (CISC) CPUs have a much larger
set of operation codes.  Your laptop probably contains a CPU
from Intel X86 family, which follows the CISC design.

We'll declare an enumeration to associate the names of the
DM2022W instruction codes with their internal representation
as integers:

```python
# The following operation codes control both the ALU and some
# other parts of the CPU.  
# ADD, SUB, MUL, DIV, SHL, SHR are ALU-only operations
# HALT, LOAD, STORE involve other parts of the CPU

class OpCode(Enum):
    """The operation codes specify what the CPU and ALU should do."""
    # CPU control (beyond ALU)
    HALT = 0    # Stop the computer simulation (in Duck Machine project)
    LOAD = 1    # Transfer from memory to register
    STORE = 2   # Transfer from register to memory
    # ALU operations
    ADD = 3     # Addition
    SUB = 5     # Subtraction
    MUL = 6     # Multiplication
    DIV = 7     # Integer division (like // in Python)
```

As you can see, we have only 7 different instruction codes.
We could have fit all of these codes into 3 bits, but we
set aside 5 in the instruction word.  Evidently the chip
designers have grand plans for future generations of
compatible chips.

### Condition Codes

DM2022W instructions are *predicated*.  This means that an
instruction may be executed or skipped depending on what
happened in the prior instruction.  The CPU will contain
a *condition register* that records information about
the result of the prior ALU operation:  Was it zero, positive,
negative, or an "overflow" (e.g., division by zero).
Each instruction contains a set of bits that are identical
in format to the condition register. If any of the
conditions specified in the `cond` field of the instruction
are recorded as true in the CPU condition register, the
instruction is executed, otherwise it is skipped.

For condition codes (as represented both in the CPU
condition register and in the *cond* field of an instruction)
we can use a special kind of enumeration called a *Flag*.
A Flag enumeration is just an integer in which we treat each
individual bit like a boolean variable.

```python
class CondFlag(Flag):
    """The condition mask in an instruction and the format
    of the condition code register are the same, so we can 
    logically and them to predicate an instruction. 
    """
    M = 1  # Minus (negative)
    Z = 2  # Zero
    P = 4  # Positive
    V = 8  # Overflow (arithmetic error, e.g., divide by zero)
    NEVER = 0
    ALWAYS = M | Z | P | V
```

Note that the values we have chosen are powers of two,
which correspond to bit positions in the condition code.
The *M* (minus) flag is the low-order bit, the *Z* (zero) flag
is bit 1, *P* (positive) is bit 2, and *V* (overflow) is bit 3.
A single *CondFlag* object can include more than one of
these flag values using bitwise logical operations, e.g.,
 we can represent "non-negative result"
as ``CondFlag.Z | CondFlag.P``.   Two such combinations
are defined in the *CondFlag* class:  ``CondFlag.NEVER``
is a *CondFlag* object in which all of the bits are zero,
and ``CondFlag.ALWAYS`` is a *CondFlag* object in which all
of the bits are one.

When we print *CondFlag* objects, we would rather not see a
value like 13 and have to figure out that it must be
a combnation of the *M*, *P*, and *V* flags.  We'll define a
``__str__`` method that produces a nicer printed format.

```python
    def __str__(self):
        """
        If the exact combination has a name, we return that.
        Otherwise, we combine bits, e.g., ZP for non-negative.
        """
        for i in CondFlag:
            if i is self:
                return i.name
        # No exact alias; give name as sequence of bit names
        bits = []
        for i in CondFlag:
            # The following test is designed to exclude
            # the special combinations 'NEVER' and 'ALWAYS'
            masked = self & i
            if masked and masked is i:
                bits.append(i.name)
        return "".join(bits)
```

Let's begin a test suite for the CPU and write a couple
of test cases for the *CondFlag* class.

```python
"""
File: test_cpu.py
Test cases for the CPU, including
some indvidual components and definitions.
"""

from instr_format import *
import unittest

class TestCondCodes(unittest.TestCase):
    """Condition flags are essentially like single bit bitfields"""

    def test_combine_flags(self):
        non_zero = CondFlag.P | CondFlag.M
        self.assertEqual(str(non_zero), "MP")
        positive = CondFlag.P
        self.assertEqual(str(positive), "P")
        self.assertEqual(str(CondFlag.ALWAYS), "ALWAYS")
        self.assertEqual(str(CondFlag.NEVER), "NEVER")
        # We test overlap of two CondFlag values using bitwise AND
        self.assertTrue(positive & non_zero)
        zero = CondFlag.Z
        self.assertFalse(zero & non_zero)


if __name__ == "__main__":
    unittest.main()

```

## Register names

Three of the fields of a DM2022W instruction word specify
*registers* to be used in the instruction.  The DM2022W
has 16 registers, which we call the *register file*.
The *address* of a register is therefore a number from
0 to 15.  Two of them are special:  Register 0 will be a
special register that always holds zero, and register 15
will be the program counter.  The rest will be creatively
named r1, r2, r3, etc.  Instead of an enumeration, we'll
associate the register addresses with their names using
a dict:

```python
# Registers are numbered from 0 to 15, and have names
# like r3, r15, etc.  Two special registers have additional
# names:  r0 is called 'zero' because on the DM2022W it always
# holds value 0, and r15 is called 'pc' because it is used to
# hold the program counter.
#
NAMED_REGS = {
    "r0": 0, "zero": 0,
    "r1": 1, "r2": 2, "r3": 3, "r4": 4, "r5": 5, "r6": 6, "r7": 7, "r8": 8,
    "r9": 9, "r10": 10, "r11": 11, "r12": 12, "r13": 13, "r14": 14,
    "r15": 15, "pc": 15
    }
```

## The Instruction Class

With all of those preliminaries, we are finally ready
to define a class for objects that hold *decoded*
instructions.  An *instruction word* is just an integer.
A *decoded instruction* holds each of the parts of an
instruction word in a separate field:

```python
# A complete DM2022W instruction word, in its decoded form.  In DM2022W
# memory an instruction is just an int.  Before executing an instruction,
# we decoded it into an Instruction object so that we can more easily
# interpret its fields.
#
class Instruction(object):
    """An instruction is made up of several fields, which 
    are represented here as object fields.
    """

    def __init__(self, op: OpCode, cond: CondFlag,
                     reg_target: int, reg_src1: int,
                     reg_src2: int,
                     offset: int):
        """Assemble an instruction from its fields. """
        self.op = op
        self.cond = cond
        self.reg_target = reg_target
        self.reg_src1 = reg_src1
        self.reg_src2 = reg_src2
        self.offset = offset
        return
```

A string method will help with debugging.  We'll make it
look like an assembly language instruction:

```python
    def __str__(self):
        """String representation looks something like assembly code"""
        if self.cond is CondFlag.ALWAYS:
            cond_codes = ""
        else:
            cond_codes = "/{}".format(self.cond)

        return "{}{:4}  r{},r{},r{}[{}]".format(
            self.op.name, cond_codes,
            self.reg_target, self.reg_src1,
            self.reg_src2, self.offset)
```

That's a rather complex format, so let's write a test case to
shake out any bugs.  (In practice I had to fiddle with the
test case to match some arbitrary details like the order
in which flag letters appear and the number of spaces between
the opcode and the first operand.)

```python
class TestInstructionString(unittest.TestCase):
    """Check that we can print Instruction objects like assembly language"""

    def test_str_predicated_MUL(self):
        instr = Instruction(OpCode.MUL, CondFlag.P | CondFlag.Z,
                        NAMED_REGS["r1"], NAMED_REGS["r3"], NAMED_REGS["pc"], 42)
        self.assertEqual(str(instr), "MUL/ZP   r1,r3,r15[42]")

    def test_str_always_ADD(self):
        """Predication is not printed for the common value of ALWAYS"""
        instr = Instruction(OpCode.ADD, CondFlag.ALWAYS,
                            NAMED_REGS["zero"], NAMED_REGS["pc"], NAMED_REGS["r15"], 0)
        self.assertEqual(str(instr), "ADD      r0,r15,r15[0]")
```

## Decoding instructions

Our CPU will be executing instruction words that it fetches
from memory.  For each instruction it executes, it will need to
first convert it into an *Instruction* object.  That is
called the *decode* step of the *fetch/decode/execute* cycle
that the CPU performs over and over and over.   Now you
have all the pieces in place.  I leave to you implementation
of the ``decode`` function (not a method) that converts
an integer into an *Instruction* object:

```python
#  Interpret an integer (memory word) as an instruction.
#  This is the decode part of the fetch/decode/execute cycle of the CPU.
#
def decode(word: int) -> Instruction:
    """Decode a memory word (32 bit int) into a new Instruction.
            
    Args:
        word: a 32-bit int, the instruction to be decoded
    """
```

The logic of this function is straightforward:  Use the
BitField objects defined before (`op`, `reg_target_field`, etc.)
to extract each of the fields from ``word``, construct
a single `Instruction` object from all those fields, and return
the `Instruction` object. **Important**: remember that the 
offset field can hold both positive and negative values, so choose
the extract method carefully.


How can we test the instruction decoding?  It would help to
have the inverse operation, a way of converting an `Instruction`
object into a single instruction word (an integer).  That could be
useful later for building an assembler also, so we might as well
build it now.  We'll add a method to the `Instruction` class to
perform the conversion:

```python
    def encode(self) -> int:
        """Encode instruction as 32-bit integer"""
```

Like the ``decode`` function, the ``encode`` method can
make use of the `BitField` objects defined above.  And therein lies
a weakness for testing:  If we make an error in one, there is a
good chance we'll make a corresponding error in the other and fail
to catch it with test cases.  But it's the best we can do for now.
Using ``decode`` and ``encode`` together may catch at least a
few errors.  Here is a test case that uses them that way:

```python
class TestDecode(unittest.TestCase):
    """Encoding and decoding should be inverses"""
    def test_encode(self):
        instr = Instruction(OpCode.SUB, CondFlag.M | CondFlag.Z, NAMED_REGS["r2"], NAMED_REGS["r1"], NAMED_REGS["r3"], -12)
        self.assertEqual(instr.encode(), 0x14C84FF4)
                        
    def test_decode(self):
        # ADD/M r15,r0,r15[-3]
        instr = Instruction(OpCode.ADD, CondFlag.M, NAMED_REGS["r15"], NAMED_REGS["r0"], NAMED_REGS["r15"], -3)
        self.assertEqual(str(decode(0xc7c3ffd)), str(instr))

    def test_encode_decode(self):
        instr = Instruction(OpCode.SUB, CondFlag.M | CondFlag.Z, NAMED_REGS["r2"], NAMED_REGS["r1"], NAMED_REGS["r3"], -12)
        text = str(decode(0x14C84FF4))    # should be "SUB/MZ   r2,r1,r3[-12]"
        self.assertEqual(text, str(instr))
```

## Building the CPU

Now that we have an instruction decoder, we can start
constructing the CPU.  We'll keep it in ``cpu.py``:

```python
"""
Duck Machine model DM2022W CPU
"""

from instr_format import Instruction, OpCode, CondFlag, decode
from typing import Tuple
```

The CPU will need to use a `Memory` and `Register`s from
modules that I have provided, as well as model-view-controller
components for displaying the CPU state.

```python
from memory import Memory
from register import Register, ZeroRegister
from mvc import MVCEvent, MVCObservable
```

For debugging we may want to log some events, so we'll
import and configure the logging module:

```python
import logging
logging.basicConfig(level = logging.DEBUG)
log = logging.getLogger(__name__)
```

Before we build the main CPU, we can build the ALU component
of the CPU.  The ALU is where calculations like addition, subtraction,
multiplication, and division take place.

```python
class ALU(object):
    """The arithmetic logic unit (also called a "functional unit"
    in a modern CPU) executes a selected function but does not
    otherwise manage CPU state. A modern CPU core may have several
    ALUs to boost performance by performing multiple operatons
    in parallel, but the Duck Machine has just one ALU in one core.
    """
    # The ALU chooses one operation to apply based on a provided
    # operation code.  These are just simple functions of two arguments;
    # in hardware we would use a multiplexer circuit to connect the
    # inputs and output to the selected circuitry for each operation.
    ALU_OPS = {
        OpCode.ADD: lambda x, y: x + y,
        # FIXME:  We need subtraction, multiplication, division
        # For division, use // for floor division
        # 
        # For memory access operations load, store, the ALU
        # performs the address calculation
        OpCode.LOAD: lambda x, y: x + y,
        OpCode.STORE: lambda x, y: x + y,
        # Some operations perform no operation
        OpCode.HALT: lambda x, y: 0
    }
```

I have left a few opcodes for you to fill in. They are
very simple!

Execution of operation is slightly more complicated.  We
need to return *two* things:  Not only the result (e.g.,
the sum of the two operands if the operation code is
```OpCode.ADD``), but also the resulting condition code.

```python
    def exec(self, op: OpCode, in1: int, in2: int) -> Tuple[int, CondFlag]:
```

``exec`` will simply look up ``op`` in the ``ALU_OPS``
table and apply the corresponding function.  We'll wrap it in a
try/except, return the tuple ``(0, CondFlag.V)`` if there
is an exception (e.g., division by zero).  If the
operation does not fail, then ``exec`` must choose
one of the other condition flags: ``CondFlag.Z`` if the
result is zero, ``CondFlag.M`` if the result is negative,
or ``CondFlag.P`` if the result is positive.   I leave that to
you.

Although the *ALU* class is fairly simple, we should at least
test to see that it is returning the results we expect,
including condition codes.
We will add test cases for ``cpu.py`` to ``test_cpu.py``,
adding an import statement:

```python
from cpu import * 
```

Then we can add a simple smoke test for the ``ALU``:

```python
class TestALU(unittest.TestCase):
    """Simple smoke test of each ALU op"""

    def test_each_op(self):
        alu = ALU()
        # The main computational ops
        # Addition  (Overflow is not modeled)
        self.assertEqual(alu.exec(OpCode.ADD, 5, 3), (8, CondFlag.P))
        self.assertEqual(alu.exec(OpCode.ADD, -5, 3), (-2, CondFlag.M))
        self.assertEqual(alu.exec(OpCode.ADD, -10, 10), (0, CondFlag.Z))
        # Subtraction (Overflow is not modeled)
        self.assertEqual(alu.exec(OpCode.SUB, 5, 3), (2, CondFlag.P))
        self.assertEqual(alu.exec(OpCode.SUB, 3, 5), (-2, CondFlag.M))
        self.assertEqual(alu.exec(OpCode.SUB, 3, 3), (0, CondFlag.Z))
        # Multiplication (Overflow is not modeled)
        self.assertEqual(alu.exec(OpCode.MUL, 3, 5), (15, CondFlag.P))
        self.assertEqual(alu.exec(OpCode.MUL, -3, 5), (-15, CondFlag.M))
        self.assertEqual(alu.exec(OpCode.MUL, 0, 22), (0, CondFlag.Z))
        # Division (can overflow with division by zero
        self.assertEqual(alu.exec(OpCode.DIV, 5, 3), (1, CondFlag.P))
        self.assertEqual(alu.exec(OpCode.DIV, 12, -3), (-4, CondFlag.M))
        self.assertEqual(alu.exec(OpCode.DIV, 3, 4), (0, CondFlag.Z))
        self.assertEqual(alu.exec(OpCode.DIV, 12, 0), (0, CondFlag.V))
        #
        # For other ops, we just want to make sure they have table
        # entries and perform the right operation. Condition code is returned but not used
        self.assertEqual(alu.exec(OpCode.LOAD, 12, 13), (25, CondFlag.P))
        self.assertEqual(alu.exec(OpCode.STORE, 27, 13), (40, CondFlag.P))
        self.assertEqual(alu.exec(OpCode.HALT, 99, 98), (0, CondFlag.Z))
```

## The CPU Itself

We are ready at last to create the central processing unit (CPU) itself.

The view component expects to receive notification of
`CPUStep` events.

```python
class CPUStep(MVCEvent):
    """CPU is beginning step with PC at a given address"""
    def __init__(self, subject: "CPU", pc_addr: int,
                 instr_word: int, instr: Instruction)-> None:
        self.subject = subject
        self.pc_addr = pc_addr
        self.instr_word = instr_word
        self.instr = instr
```

The `CPU` class can then inherit the standard model-view-containiner mechanisms
(keeping a list of observers) from the `MVCObservable` class defined in ``mvc.py``.

```python
class CPU(MVCObservable):
    """Duck Machine central processing unit (CPU)
    has 16 registers (including r0 that always holds zero
    and r15 that holds the program counter), a few
    flag registers (condition codes, halted state),
    and some logic for sequencing execution.  The CPU
    does not contain the main memory but has a bus connecting
    it to a separate memory.
    """
```

Memory is not part of the CPU, but the CPU communicates with a memory unit
over a bus.  In ``duck_machine.py`` the memory unit is created and then
passed to the constructor of class ``CPU`` to set up that communication.
(It's actually a ``MemoryMappedIO``, but the CPU treats it as a regular
memory.  The CPU doesn't know about input/output!)

```python
    def __init__(self, memory: Memory):
        super().__init__()
        self.memory = memory  # Not part of CPU; what we really have is a connection
```

The CPU also needs 16 registers, one of which is the special *zero* register that
always holds zero.  We could create them in a loop, but 16 is a pretty small number ...
we can just create the ``Register`` objects in a list literal:

```python
        self.registers = [ ZeroRegister(), Register(), Register(), Register(),
                           Register(), Register(), Register(), Register(),
                           Register(), Register(), Register(), Register(),
                           Register(), Register(), Register(), Register() ]
```

In addition, we need to keep track of the condition code of the prior instruction,
and whether or not the CPU is halted.   We'll initialize the condition code to
``ALWAYS`` so that the first instruction in a program will always be executed,
regardless of the condition flags in its condition field.

```python
        self.condition = CondFlag.ALWAYS
        self.halted = False
```

Finally, we need an ALU object to perform calculations:

```python
        self.alu = ALU()
```

You might choose to create ``self.pc`` as an alias to ``self.registers[15]``, as I did,
but that is up to you.

## Step the CPU

The heart of the CPU's sequencing logic is the ``step`` method, which carries out
one fetch/decode/execute cycle.

```python
   def step(self):
```

The fetch phase of the cycle reads an instruction word
from memory.  The decode phase, as you might surmise, decodes the instruction word
into an ``Instruction`` object.  The execute phase then does whatever that instruction
calls for.

### Fetch

To fetch an instruction, first we get the address from register 15, using the ``get`` method of the
``Register`` class.  Then we use that address to read the instruction word from memory,
using the ``get`` method of the ``Memory`` class.   I'll leave that to you.

### Decode

You've already done the hard work of decoding, mostly last week.  Just call the
``decode`` function you wrote earlier to get an *Instruction* object.  If your
*fetch* phase left the instruction address in  ``instr_addr`` and the instruction
word in ``instr_word``, your *decode* phase could look like this:

```python
        # Decode
        instr = decode(instr_word)
```

Before going on to the *execute* phase, we want to send an event to the *view* component
to display instruction in progress:

```python
        # Display the CPU state when we have decoded the instruction,
        # before we have executed it
        self.notify_all(CPUStep(self, instr_addr, instr_word, instr))
```

### Execute

The execution phase must be carefully sequenced.

* First we check the instruction predicate.  We use
  a bitwise *and* (``&``) between the CPU condition code (`self.condition`) and
  the ``condition`` field of the instruction (`instr.cond`).   What
  happens next depends on whether the result is positive (meaning
  at least one of the condition bits that are 1 in the
  instruction predicate is true of the CPU condition) or 0
  (the CPU condition does not match any of the predicate
  bits in the instruction).  We'll say the condition is
  *satisfied* if the result is positive.


  * If the result of
    the bitwise *and* is positive, we perform the specified
    operation.  The left operand will be the contents
    of the register specified by ``instr.reg_src1``; we
    call the ``get`` method on that register to obtain
    its value.   The right operand will be the sum of
    the ``instr.offset`` field and the contents of
    the register specified by ``instr.reg_src2``.
  * We calculate a result value and new condition code
    by calling the ALU ``exec`` method, giving it
    ``instr.op`` and the two operand values.
  * *BEFORE* we save the result value and instruction
    code, we increment the program counter (register 15, 
    also aliased as `self.pc` in the CPU class).
  * Then, after incrementing the program counter, we
    complete the operation.

    * If the operation was STORE, we use the result
      of the calculation as a memory address, and save the
      value of the register specified by ``instr.reg_target``
      to that location in memory.
    * If the operation was LOAD, we use use the result
      of the calculation as a memory address, and fetch
      the value of that location in memory, storing
      it in the register specified by ``instr.reg_target``.
    * If the operation was HALT, we set the halt
      flag (``self.halted``) to ``True``.
    * For the other operations (ADD, SUB, MUL, DIV) we
      store the result of the calculation in the register
      specified by ``instr.reg_target`` and store the
      new condition code in the ``condition`` field of
      the CPU.
  * Otherwise, if the predicate was not satisfied,
    we skip most of those steps and just increment register 15.

I will leave implementation of ``execute`` to you.  Try to
figure it out, but then ask questions if you have trouble.
To give you a rough idea of what to expect, my ``step`` method
implementation is about 40 lines, and about half of those
are blank lines, comment lines, and debugging statements
(calls to ``log.debug("your message here")``, but first make sure that
the logging level is loggging.DEBUG everywhere, including in 
`duck_machine.py`).

While I'd like to have some nice stand-alone test cases for
the ``step`` method, they are difficult to set up because
they involve the complete state of the CPU and memory.  We'll
be able to test very shortly by executing DM2022W programs.

### Run

The ``run`` method is just a loop that executes the
fetch/decode/execute cycle of ``step`` over and over again.
We can use an optional argument for single-stepping the
CPU, which is sometimes useful in debugging.
I'll provide this method so that we can get on with testing:

```python
    def run(self, from_addr=0,  single_step=False) -> None:
        self.halted = False
        self.pc.put(from_addr)
        step_count = 0
        while not self.halted:
            if single_step:
                input("Step {}; press enter".format(step_count))
            self.step()
            step_count += 1
```

## Let's RUN!

At this point, we should have a full working Duck Machine.
Instead of unit tests, we can test it by running programs.
``duck_machine.py`` can be run from the command line.
``programs/max.obj`` is a good test.

```
$ python3 duck_machine.py programs/max.obj 
Quack! Gimme an int! 5
Quack! Gimme an int! 18 
Quack!: 18
Halted
```

With the ``-d`` flag in the command, we can watch the internal
state of the CPU and memory as it executes.  With the -s flag, we
can "single step" the CPU through execution.

```bash
l$ python3 duck_machine.py programs/max.obj -d -s 
Step 0; press enter
Quack! Gimme an int! 13
Step 1; press enter
Quack! Gimme an int! 22
Step 2; press enter
Step 3; press enter
Step 4; press enter
Quack!: 22
Step 5; press enter
Halted
Press enter to end
```

![CPU state display](cpu-state.png)

## Hints (Fixing Common Problems)

* When decoding instructions, don't forget to convert ints representing op code and cond code to
  objects of class `OpCode` and `CondFlag`, respectively.
* When decoding instructions, remember to use `extract_signed` for the offset field.
* When encoding, use `self.op.value` and `self.cond.value` to
  get the integer value of op code and cond code.
* In `ALU_OPS`, don't forget to use integer division (`//`) rather than floating point division (`/`).
* Remember how to obtain the information from a register or memory:
  using `Register.get()` and `Memory.get(index)`. 
  Similar for saving information in a register or memory: `Register.put(value)` and `Memory.put(index, value)`.
  (And remember when we write `Class.method(v)` what we really mean is `o.method(x)` for some object `o`
  with class `Class` and some expression `x` with the value to use for `v`.)
  For example, if you are in a `CPU` class method and want to get the value of register 3, you would use `self.registers[3].get()`.
