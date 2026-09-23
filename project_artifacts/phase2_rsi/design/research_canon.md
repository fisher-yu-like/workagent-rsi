# Phase 2 Research Canon

## Hard facts

- WorkAgent-RSI defines RSI as Recursive Skill Improvement at the agent-system level.
- The mutable object is a versioned Office skill and its harness configuration, not the backbone model weights in the initial research stage.
- Phase 1B implemented and executed a deterministic mock Harness pipeline. It did not execute an external WorkAgent provider or real Office task.
- The initial target domains are Excel, Word and PowerPoint.
- The local machine has Windows 11, an Intel Core i7-14650HX, 16 GB RAM and an NVIDIA GeForce RTX 5060 Laptop GPU with 8 GB VRAM.
- The two primary references are arXiv:2609.24972 and arXiv:2609.11873. Both are preprints.

## Fixed project boundaries

- `gen-skill` may propose candidates but cannot publish them.
- Candidate-controlled code cannot modify the evaluator, hidden tests, promotion policy, tool allowlist or immutable evidence.
- Evaluation uses hard assertions first, then structure/visual checks, then semantic judgement.
- Training, hidden, regression and transfer splits remain logically separate.
- Phase 2 produces a design and executable plan. It does not claim training or experimental scores.

## Open facts for Phase 3

- Concrete WorkAgent provider and model.
- Licensed benchmark datasets and final sample counts.
- API pricing and available budget.
- Office recalculation/rendering engine used for formal experiments.
