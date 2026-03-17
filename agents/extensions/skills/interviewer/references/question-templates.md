# Question Templates

Reference patterns for generating interview questions across different types and difficulty levels.

## Conceptual Questions

### Pattern: Explain Mechanism
- "Explain how [X] works and why it's used in [context]."
- "Walk me through the [X] process from start to finish."
- "What happens under the hood when [action] occurs?"

**Examples:**
- L1: "Explain how a neural network makes a prediction."
- L2: "Explain how backpropagation computes gradients."
- L3: "Explain how attention mechanisms allow transformers to capture long-range dependencies."
- L4: "Explain how flash attention reduces memory complexity from O(n²) to O(n)."

### Pattern: Compare and Contrast
- "Compare [X] vs [Y] - what are the trade-offs?"
- "When would you choose [X] over [Y]?"
- "What are the key differences between [X] and [Y]?"

**Examples:**
- L1: "Compare batch gradient descent vs stochastic gradient descent."
- L2: "Compare RNNs and LSTMs - what problem do LSTMs solve?"
- L3: "Compare encoder-only, decoder-only, and encoder-decoder transformers."
- L4: "Compare tensor parallelism vs pipeline parallelism for LLM training."

### Pattern: Problem-Solution
- "Why does [problem] occur and how is it addressed?"
- "What causes [issue] and what techniques mitigate it?"
- "How do we handle [challenge] in practice?"

**Examples:**
- L1: "Why does overfitting occur and how do we prevent it?"
- L2: "What is the vanishing gradient problem and how do residual connections help?"
- L3: "Why does catastrophic forgetting happen during fine-tuning and how do we mitigate it?"
- L4: "What causes training instability at scale and how do techniques like μP help?"

### Pattern: Why/Intuition
- "Why is [X] important/necessary?"
- "What's the intuition behind [technique]?"
- "Why does [approach] work better than [alternative]?"

**Examples:**
- L1: "Why do we use non-linear activation functions?"
- L2: "What's the intuition behind dropout regularization?"
- L3: "Why does layer normalization help transformer training?"
- L4: "Why does the Chinchilla scaling law suggest different compute allocation than GPT-3?"

## Implementation Questions

### Pattern: Algorithm Walkthrough
- "Walk me through how you would implement [X]."
- "Describe the steps to build [component]."
- "How would you code [algorithm] from scratch?"

**Examples:**
- L1: "Walk me through implementing forward propagation for a single layer."
- L2: "How would you implement mini-batch gradient descent with momentum?"
- L3: "Walk me through implementing multi-head attention."
- L4: "How would you implement gradient checkpointing for memory efficiency?"

### Pattern: Pseudocode
- "Write pseudocode for [algorithm]."
- "Sketch out the code structure for [component]."
- "What would the main loop look like for [process]?"

**Examples:**
- L1: "Write pseudocode for a simple training loop."
- L2: "Write pseudocode for the softmax function with numerical stability."
- L3: "Write pseudocode for beam search decoding."
- L4: "Write pseudocode for KV-cache management in batched inference."

### Pattern: Complexity Analysis
- "What's the time/space complexity of [approach]?"
- "How does [algorithm] scale with [parameter]?"
- "What are the computational bottlenecks in [process]?"

**Examples:**
- L1: "What's the time complexity of matrix multiplication in a linear layer?"
- L2: "How does training time scale with batch size?"
- L3: "What's the memory complexity of self-attention with respect to sequence length?"
- L4: "Analyze the computation vs communication trade-offs in distributed training."

### Pattern: Debug/Fix
- "This [code/approach] has a bug - what's wrong?"
- "Why might [implementation] produce [unexpected result]?"
- "How would you debug [issue] in training?"

**Examples:**
- L1: "Why might a model's loss be NaN?"
- L2: "This attention implementation is slow - what's the likely issue?"
- L3: "Training loss is oscillating wildly - what could cause this?"
- L4: "Gradient norms are exploding only on certain layers - what's happening?"

## Design Questions

### Pattern: System Design
- "Design a system that [requirement]."
- "How would you architect [application]?"
- "What components would you need for [use case]?"

**Examples:**
- L1: "Design a simple image classification pipeline."
- L2: "Design a sentiment analysis system for customer reviews."
- L3: "Design an LLM serving system that handles variable-length requests."
- L4: "Design a training infrastructure for a 100B parameter model."

### Pattern: Scale/Optimize
- "How would you scale [X] to handle [constraint]?"
- "How would you optimize [system] for [metric]?"
- "What would you change to improve [aspect]?"

**Examples:**
- L1: "How would you handle a dataset that doesn't fit in memory?"
- L2: "How would you reduce inference latency for a production model?"
- L3: "How would you scale training to multiple GPUs?"
- L4: "How would you optimize for cost-per-token in a multi-tenant LLM service?"

### Pattern: Architecture Choice
- "What architecture would you use for [use case]?"
- "How would you choose between [options] for [problem]?"
- "What model design decisions matter most for [application]?"

**Examples:**
- L1: "Should you use a CNN or MLP for image classification? Why?"
- L2: "When would you use a pre-trained model vs training from scratch?"
- L3: "How would you choose between fine-tuning and prompting for a new task?"
- L4: "How would you decide between MoE and dense models for your use case?"

## Trade-off Analysis Questions

### Pattern: Decision Framework
- "When would you choose [X] over [Y]?"
- "What factors would influence choosing [approach]?"
- "Under what conditions does [method] work best?"

**Examples:**
- L1: "When would you use L1 vs L2 regularization?"
- L2: "When would you choose Adam over SGD?"
- L3: "When is LoRA better than full fine-tuning?"
- L4: "When would you use speculative decoding vs standard autoregressive generation?"

### Pattern: Limitations
- "What are the limitations of [approach]?"
- "Where does [method] fail or struggle?"
- "What are the drawbacks of [technique]?"

**Examples:**
- L1: "What are the limitations of accuracy as an evaluation metric?"
- L2: "What are the drawbacks of using dropout during inference?"
- L3: "What are the limitations of BLEU for evaluating language models?"
- L4: "What are the failure modes of RLHF alignment?"

### Pattern: Production Considerations
- "How does [X] affect [Y] in production?"
- "What changes when moving from research to production?"
- "What operational concerns arise with [approach]?"

**Examples:**
- L1: "How does model size affect deployment options?"
- L2: "What monitoring would you set up for a production ML model?"
- L3: "How do you handle model versioning and rollbacks?"
- L4: "What are the operational challenges of serving MoE models?"

## Paper/Material-Based Questions

Use when user provides source files or specific papers.

### Pattern: Key Contribution
- "What is the key contribution of [paper/section]?"
- "What problem does [approach] solve that prior work didn't?"
- "What's novel about [method] compared to previous approaches?"

### Pattern: Method Deep-Dive
- "Explain the [specific technique] described in [source]."
- "How does [method] work according to [paper]?"
- "Walk me through the [algorithm] as presented in [material]."

### Pattern: Critical Analysis
- "What are potential weaknesses of [approach] from [paper]?"
- "How might [method] fail in scenarios not covered?"
- "What assumptions does [technique] make that might not hold?"

### Pattern: Connection to Broader Field
- "How does [paper's approach] relate to [other technique]?"
- "Where does [method] fit in the landscape of [field]?"
- "What subsequent work built on [paper's] ideas?"

## Follow-Up Patterns

For multi-part or progressive question formats.

### Deepening
- Initial: "Explain [concept]."
- Follow-up: "Now, how does that change when [constraint/condition]?"

### Application
- Initial: "What is [technique]?"
- Follow-up: "How would you apply that to [specific scenario]?"

### Edge Cases
- Initial: "Describe [algorithm]."
- Follow-up: "What happens when [edge case]?"

### Implementation Detail
- Initial: "How does [system] work?"
- Follow-up: "How would you actually implement [specific component]?"

### Scale
- Initial: "Explain [approach]."
- Follow-up: "How does this change at [larger scale]?"

## Topic-Specific Templates

### LLM-Focused Topics

**Architecture:**
- "Explain the role of [positional encoding/attention/FFN] in transformers."
- "How does [RoPE/ALiBi/learned positions] work?"
- "What is the purpose of the KV cache?"

**Training:**
- "Explain the difference between [pre-training/fine-tuning/RLHF]."
- "How does [DPO/PPO/GRPO] work for alignment?"
- "What is [instruction tuning/constitutional AI/RLAIF]?"

**Inference:**
- "Explain [greedy/beam/nucleus] sampling."
- "How does [speculative decoding/continuous batching] improve throughput?"
- "What is [quantization/pruning/distillation] and when would you use it?"

**Data:**
- "How do you [curate/filter/deduplicate] pre-training data?"
- "What role does [synthetic data/data mixing] play?"
- "How do you handle [toxic content/PII/copyright] in training data?"

**Systems:**
- "Explain [data/tensor/pipeline] parallelism."
- "How does [ZeRO/FSDP] reduce memory usage?"
- "What are the trade-offs of different [sharding strategies]?"

### Broader ML/AI Topics

**Classical ML:**
- "Explain [decision trees/SVMs/ensembles]."
- "When would you use [logistic regression vs neural networks]?"
- "How does [boosting/bagging] work?"

**Deep Learning Fundamentals:**
- "Explain [convolutions/pooling/batch norm]."
- "What is [the universal approximation theorem/expressiveness]?"
- "How do [skip connections/attention/normalization] help training?"

**Optimization:**
- "Explain [Adam/SGD with momentum/learning rate schedules]."
- "What is [gradient clipping/warmup/weight decay]?"
- "How do [second-order methods/natural gradient] differ from first-order?"

**Evaluation:**
- "What metrics would you use for [task type]?"
- "How do you handle [class imbalance/distribution shift]?"
- "What is [cross-validation/bootstrapping/statistical significance]?"

### General CS/Systems Topics

**Distributed Systems:**
- "Explain [consistency/availability/partition tolerance] trade-offs."
- "How does [MapReduce/Spark/Ray] handle distributed computation?"
- "What is [consensus/replication/sharding]?"

**Databases:**
- "When would you use [SQL vs NoSQL vs vector DBs]?"
- "How does [indexing/caching/query optimization] work?"
- "What are [ACID properties/eventual consistency]?"

**Algorithms:**
- "What is the complexity of [sorting/searching/graph algorithm]?"
- "When would you use [dynamic programming/greedy/divide-and-conquer]?"
- "Explain [hash tables/trees/heaps] and their trade-offs."

## Difficulty Calibration

### L1 (Foundational)
- Textbook definitions
- Single-concept explanations
- Basic "what is X" questions
- Simple comparisons

### L2 (Intermediate)
- Multi-concept connections
- "How does X work" with some depth
- Common trade-offs
- Standard implementation questions

### L3 (Advanced)
- System-level thinking
- Non-obvious trade-offs
- Production considerations
- Multi-step reasoning

### L4 (Expert)
- Cutting-edge techniques
- Scaling challenges
- Research frontiers
- Complex system design

## Hint Patterns

When user needs help:

**Conceptual hints:**
- "Think about what [component] is trying to achieve..."
- "Consider the relationship between [X] and [Y]..."
- "What would happen without [element]?"

**Implementation hints:**
- "Start by considering the inputs and outputs..."
- "Break it down into smaller steps..."
- "What's the base case?"

**Design hints:**
- "What are the main requirements to satisfy?"
- "Consider the bottleneck first..."
- "What would a simple version look like?"

## Breaking Down Questions

When user says "I don't know":

1. **Identify the gap:** "Which part is unclear - the [X] or the [Y]?"
2. **Simplify:** "Let's start simpler - do you know what [prerequisite concept] is?"
3. **Concrete example:** "Let's think about a specific example: [scenario]"
4. **Build up:** "If [simpler case], what would change for [original question]?"
