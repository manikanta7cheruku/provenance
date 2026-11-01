# Carryover

Work that was built and tested but could not be finished or proven during a checkpoint, because it needs something only the owner can supply (a real AI key, a real person, a real device, a decision) or because it belongs to a later checkpoint. Each item has the phase and checkpoint that created it, why it is open, and exactly how to close it.

The plan is to do all of this together at the end of the build, before any release. Nothing here blocks building the next checkpoint.

- [register.md](register.md): every open item, with its ID, checkpoint, why, how to close it and its state.
- [real-ai-model-setup.md](real-ai-model-setup.md): the step by step to turn the real AI model on and what to measure in each checkpoint that depends on it.

## Rules
1. Every checkpoint that leaves something open adds it to the register in the same commit. Say what was not verified in the checkpoint document too.
2. An item is closed only when its "How to close" steps were run and the result is written next to it with a date.
3. An item that turns out to be wrong or unnecessary is struck out with the reason, not deleted.
4. Do not paste personal data, resume text or keys into this folder. Use ids, counts and measurements.
