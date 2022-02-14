#
# A first DM2022W program.  This program uses only sequential
# control flow (no predication or branching) and only affects
# registers.  When the program halts, we should see that register
# 1 contains value 1, register 2 contains value 2, and register
# 3 contains value 3. 
#
   ADD  r1,r0,r0[1]    # r1 = 1
   ADD  r2,r0,r0[2]    # r2 = 2
   ADD  r3,r1,r2       # r3 = r1 + r2
   HALT r0,r0,r0
   
   
