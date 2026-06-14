# The Hidden Algorithms: A Deep Dive into Vector Database Internals

*Explains the core computer science behind vector databases, including HNSW indexing, distance metrics (cosine vs Euclidean), and quantization for performance, targeting software engineers wanting to understand the 'how it works' to make informed architectural decisions.*

**Estimated read time:** 17 min  

---


---

## Beyond the Black Box: Why Internals Matter

From the outside, a vector database looks like magic. You hand it embeddings, submit a query, and it returns the most similar items in milliseconds. That abstraction is convenient during prototyping. In production, with millions of vectors, sub-100ms latency targets, and tight memory budgets, the black box becomes a liability. Understanding what the database does internally is necessary for tuning performance, controlling cost, and making sound architectural decisions.

The vector database market has expanded rapidly. A 2024 survey identifies over twenty systems, most developed within the past five years. Each offers different indexing, compression, and query strategies. Selecting one and configuring it correctly demands more than a surface-level grasp of k-NN APIs. A default setup can allocate too much memory, miss latency targets, or silently degrade recall.

The stakes are magnified by modern applications. In retrieval-augmented generation, a user prompt is embedded, the system searches a vector store for relevant context, and passes it to a large language model. If the search step is slow or returns irrelevant chunks, the entire experience suffers and costs climb. A misconfigured vector database can make the difference between a responsive, affordable product and one that misses its SLAs entirely.

This article rests on a specific claim: engineers who spend hours debating cosine similarity versus Euclidean distance are optimizing the wrong thing. When vectors are normalized, the standard post-processing step for most modern embedding models, including those from OpenAI and sentence transformers, cosine similarity and Euclidean distance produce identical nearest-neighbor orderings. The accuracy and latency of a vector search system are overwhelmingly determined by the quantization strategy and HNSW index parameters, not the distance metric. Tuning those typically has a far larger effect on recall and throughput than switching between cosine and Euclidean.

This does not mean the distance metric never matters. For unnormalized vectors, raw word embeddings or custom feature vectors where magnitude carries meaning, cosine and Euclidean are not equivalent. Choosing incorrectly can favor documents by length rather than semantic content. If your vectors are unnormalized, you must pick the right metric. In the vast majority of modern production pipelines, however, normalization nullifies the choice, freeing you to concentrate on what actually moves the needle.

The internals follow a recognizable pipeline. Vectors arrive from an embedding model, usually normalized to unit length. They are inserted into an index, often a Hierarchical Navigable Small World graph, that organizes them for fast approximate nearest-neighbor search. To reduce memory, the vectors are compressed with quantization. At query time, the query vector is mapped through the same index, the system retrieves candidates, and a distance metric ranks them to return the top k.

Each stage in this pipeline is a dial that shifts the balance among speed, accuracy, and memory. The index graph parameters control how many connections each node makes and how deeply the search explores. Quantization determines the precision of stored vectors. The metric sets the notion of closeness. Tweaking these knobs without understanding their interaction leads to guesswork. The sections that follow dissect each stage: first, the construction and search mechanics of HNSW; then the mathematics of similarity and the quantization tricks that compress vectors; and finally, the real-world tradeoffs that emerge when you put them together.

---

## The Index: How HNSW Builds a Navigable Small World

Brute-force nearest-neighbor search must scan every stored vector, comparing each against a query. For 10 million 768-dimensional embeddings, that is 7.68 billion floating-point operations per query, far too slow for interactive applications. Approximate Nearest Neighbor (ANN) indexes trade a small amount of accuracy for orders of magnitude faster retrieval. The algorithm that dominates production vector databases today is Hierarchical Navigable Small World (HNSW). The deeper question for an engineer tuning a production system is not just how HNSW works; it is why those structural details swamp the impact of the distance metric when vectors are normalized. Understanding the internal levers of HNSW shows that recall, latency, and memory consumption are determined overwhelmingly by the index parameters.

### The hierarchical small-world graph

HNSW builds a multi-layer graph. The bottom layer (layer 0) contains every inserted vector. Each higher layer holds an exponentially smaller subset of points. This design allows a search to skip across large regions quickly in the sparse upper layers, then refine at finer granularity in the dense bottom layer.

Layer assignment for a new vector is probabilistic, governed by a normalized exponential decay. In the standard implementation, a vector's maximum layer *L* is determined by

```
L = ⌊ -ln(uniform(0,1)) ⋅ mL ⌋
```

where *mL* is a normalization factor, typically *1/ln(M)* for the graph parameter *M*. The probability that a node reaches layer *l* is *P(l) = (1 - e^{-1/mL}) · e^{-l/mL}*. As an illustration, with *M=16* the expected maximum level is *mL ≈ 0.36*, and roughly 0.4 % of nodes land at layer 2 or above. Nodes on higher layers become long-range bridges. The node with the highest level ever assigned becomes the single *entry point* from which every search and insertion starts.

Because the level distribution depends only on *M* and random chance, the graph topology is independent of the distance metric. Whether the graph stores L2-normalized embeddings and uses inner product, or the same embeddings and Euclidean distance, the set of node positions is identical. We will see why that makes the metric choice irrelevant for the vast majority of production systems.

### Insertion: building the graph one vector at a time

HNSW constructs the index incrementally. When a new vector arrives, the procedure follows these steps:

1. **Determine the maximum layer** using the exponential-decay rule. If the assigned layer exceeds the current highest layer, create empty layers above and make this vector the new entry point.
2. **Greedy descent.** Starting at the entry point on the top layer, move to the neighbor whose vector is closest to the new point, repeating until no neighbor is closer. That node becomes the "enter point" for the next layer down.
3. **Insert in the appropriate layers.** At each layer from the vector's own maximum layer down to layer 0, collect the *ef_construction* nearest neighbors using a limited beam search. Connect the new node to the *M* closest among them. If any neighbor already has *M* connections, prune the longest edge after adding the new link to keep the maximum degree constant.
4. **Repeat for lower layers.** The descent continues until layer 0, where every vector is placed.

A walk-through with concrete points clarifies the process. Suppose we index five normalized 2-dimensional vectors and use Euclidean distance:

| Point | Coordinates (x, y) | Assigned maximum layer |
|-------|--------------------|------------------------|
| A | (0.10, 0.99) | 2 (becomes entry point)|
| B | (0.20, 0.98) | 0 |
| C | (0.85, 0.53) | 1 |
| D | (0.71, 0.70) | 0 |
| E | (0.33, 0.94) | 0 |

**Step-by-step insertion:**

- A arrives, lands at layer 2, becomes the entry point. No edges yet.
- B (layer 0): descent from A at layer 2, A is nearest. At layer 0, B searches for *ef_construction* neighbors; still only A exists, so A-B edge is created in layer 0.
- C (layer 1): descent from A at layer 2 to A at layer 1. At layer 1 (C's top layer), search finds A as nearest; C connects to A in layer 1. Then layer 0: descent through A, search finds neighbors A and B; C connects to M nearest (both if M≥2).
- D (layer 0): descent passes through A (layer 2) to C (layer 1) to nearest in layer 0. At layer 0, D connects to A, B, C based on distance.
- E (layer 0): similar insertion at layer 0, connecting to the closest existing neighbors.

Because all vectors are normalized, the Euclidean distance between any two points is *d² = 2 - 2·cos(θ)*, a monotonic transformation of cosine similarity. The nearest-neighbor ordering is identical under both metrics. Therefore the same graph edges would be formed if the index used cosine similarity as its distance function; the topology remains unchanged. The only important condition is that the vectors are L2-normalized before insertion, which is standard for modern embedding pipelines.

### Search: descending the hierarchy

A query follows the reverse path, controlled by a search-time parameter **ef_search**:

1. **Start at the entry point** on the top layer. Greedily move to the neighbor closest to the query vector until a local minimum is reached, where no neighbor is closer than the current node.
2. **Descend one layer.** Use that local minimum as the enter point for the next layer, repeating the greedy walk.
3. **At layer 0**, perform a wider beam search: maintain a candidate set of size *ef_search*, explore their neighbors, and keep the globally closest *ef_search* vectors. The top-*k* results are returned from this set.

The upper-layer walks are cheap because the graphs are sparse. The expensive part is the beam search at layer 0, and its cost grows with *ef_search*.

### The parameters that dominate recall and latency

Three knobs shape an HNSW index. Their effect on recall dwarfs any choice between cosine and Euclidean on normalized data:

- **M** - the maximum number of outgoing edges per node. Typical values are 16 to 64. Larger *M* increases recall because each node sees more of its vicinity, but it consumes more memory and slows construction.
- **ef_construction** - the beam width used during insertion. Values of 200 to 500 are common; a higher width produces a higher-quality graph (fewer false-positive edges) at the cost of longer build time.
- **ef_search** - the beam width at query time. Setting *ef_search = k* (the requested result count) behaves like a simple greedy search, often yielding recall below 80 %. Raising it to 100 to 500 can drive recall above 99 %, while adding latency.

Consider a dataset with 1 M normalized 768-dim vectors. With M=16, ef_construction=200, and ef_search=16, the system might return an 83 % recall for a top-10 query. Keeping the same dataset and distance metric, simply raising ef_search to 128 can lift recall to 99.5 %, a gain of over 16 percentage points. Swapping the distance metric from inner product to L2 while keeping vectors normalized changes nothing at all; the 83 % recall stays 83 %. The real leverage resides in the index parameters.

The following Python snippet builds an HNSW index with Facebook's FAISS library, illustrating parameter control. The vectors are normalized and the index uses inner product, which for normalized vectors is equivalent to cosine similarity.

```python
import numpy as np
import faiss

dim = 768 # embedding dimension
nb = 100_000 # number of base vectors
M = 32 # number of connections per node
ef_construction = 200
ef_search = 128

# For normalized vectors, inner product = cosine similarity,
# because |x|=|y|=1 implies x·y = cos(θ).
# Euclidean distance: ||x-y||^2 = 2 - 2·cos(θ).
index = faiss.IndexHNSWFlat(dim, M, faiss.METRIC_INNER_PRODUCT)
index.hnsw.efConstruction = ef_construction
index.hnsw.efSearch = ef_search

# Generate and add random normalized vectors
np.random.seed(42)
xb = np.random.rand(nb, dim).astype('float32')
faiss.normalize_L2(xb)
index.add(xb)

# Search for the 5 nearest neighbours of a query vector
xq = np.random.rand(1, dim).astype('float32')
faiss.normalize_L2(xq)
k = 5
distances, labels = index.search(xq, k)
print("Indices:", labels)
print("Distances:", distances)
```

Because the vectors are L2-normalized, the distances returned (inner product values) produce the exact same ranking as Euclidean distance or cosine similarity would. The topology of the HNSW graph was built on vectors that already occupy the unit hypersphere, so the metric is effectively neutralized. This is not a special property of FAISS; any HNSW implementation that inserts normalized vectors will exhibit the same behaviour.

### From index structure to quantization

The HNSW graph itself does not compress the stored vectors; each node still holds a full-precision float vector. To reduce memory and speed up similarity computation, production systems apply quantization on top of the graph. Those quantization techniques (product quantization, scalar quantization) introduce reconstruction errors that can far exceed any subtle differences an unnormalized distance metric would produce. Consequently, the accuracy-versus-performance trade-off that senior engineers need to manage is not about cos or L2; it is about the interplay between graph parameters and quantization levels. That is the focus of the next section.

---

## The Math of Similarity: Cosine vs Euclidean and the Quantization Trick

### Cosine vs. Euclidean: When the Choice Vanishes

The two workhorses of vector comparison are Euclidean (L2) distance and cosine similarity.

Euclidean distance treats vectors as points in space. For two n-dimensional vectors \(x\) and \(y\), the squared distance is:

\[
d_E^2(x,y) = \sum_{i=1}^{n} (x_i - y_i)^2
\]

Cosine similarity measures the angle between vectors, independent of their lengths:

\[
\text{cos}(\theta) = \frac{x \cdot y}{\|x\| \|y\|}
\]

If every vector in the database is L2-normalized (unit length, \(\|x\| = 1\)), then:

\[
d_E^2(x,y) = \|x\|^2 + \|y\|^2 - 2 (x \cdot y) = 2 - 2\cos(\theta)
\]

Since \(2\) is constant, minimizing squared Euclidean distance is identical to maximizing cosine similarity. The nearest-neighbour rankings are the same. OpenAI's `text-embedding-ada-002`, all-MiniLM sentence-transformers, and most modern embedding pipelines produce normalized vectors. In those systems, swapping one metric for the other has zero effect on retrieval order. The debate over cosine vs. Euclidean is, in those cases, a distraction.

That does not hold for unnormalized vectors. Raw word2vec embeddings, sparse bag-of-feature vectors, or any representation where magnitude carries deliberate meaning require a deliberate choice. Euclidean distance will pull a long document vector closer to a short one that shares few words simply because of length. Cosine similarity, by ignoring magnitude, will favour documents with similar word distributions. If your vectors are not normalized, you must pick the metric that matches your semantics. However, in the majority of production retrieval pipelines, normalization is a standard post-processing step specifically to decouple magnitude from meaning, so the question is already resolved.

Once the metric is fixed, the real lever for memory, latency, and recall is quantization. This is where engineering time delivers orders-of-magnitude impact.

### Shrinking Vectors Without Breaking Search

Storing one million 768-dimensional float32 vectors costs roughly 3 GB of RAM. That pushes many workloads past the cache line budgets of a single machine. Scalar quantization (SQ) reduces each dimension to a lower-precision integer, say int8, achieving a 4× compression. Distance calculations still touch every dimension but use faster integer arithmetic or lookup tables, with minimal recall loss.

Product quantization (PQ) takes compression much further. The core idea, popularized by the FAISS library, is to split each vector into \(m\) subvectors. For example, a 768-dim vector can be carved into \(m=64\) subvectors of 12 dimensions each. A separate k-means clustering on each subspace produces \(k\) centroids. The database vector is then stored as \(m\) byte-sized IDs that point to the nearest centroid in each subspace. A distance look-up table precomputes the squared distances from the query's subvectors to every centroid in that subspace. The approximate distance between the query and any database vector is the sum of the precomputed distances indexed by the stored IDs.

The storage savings are dramatic. With \(m=64\) and \(k=256\), a vector shrinks from 3072 bytes to just 64 bytes, a 97% reduction. The computation flips from a floating-point dot product to \(m\) table look-ups and additions.

The snippet below illustrates encoding and distance approximation using a pre-trained codebook. The centroids are assumed to be trained on a representative sample of vectors and loaded from storage.

```python
import numpy as np

def encode(codebooks, vector):
 """Split vector into subvectors and return the nearest centroid IDs."""
 dim_sub = codebooks.shape # dimension of each subspace
 ids = []
 for i, cb in enumerate(codebooks):
 start = i * dim_sub
 end = start + dim_sub
 sub = vector[start:end]
 ids.append(np.argmin(np.linalg.norm(cb - sub, axis=1)))
 return ids

def build_dist_table(query, codebooks):
 """Precompute squared distances from query subvectors to all centroids."""
 dim_sub = codebooks.shape
 table = []
 for i, cb in enumerate(codebooks):
 start = i * dim_sub
 end = start + dim_sub
 sub = query[start:end]
 dists = np.linalg.norm(cb - sub, axis=1) ** 2
 table.append(dists)
 return table

def approx_dist(pq_ids, dist_table):
 """Sum the precomputed distances using the stored centroid IDs."""
 return sum(table[idx] for table, idx in zip(dist_table, pq_ids))
```

PQ is not lossless. The reconstruction error grows as the number of subvectors shrinks or the number of centroids \(k\) drops. A poorly chosen PQ configuration, say too few centroids per subspace, can degrade recall by 10 to 20% or more regardless of the distance metric, a phenomenon observed across ANN benchmarks such as ann-benchmarks.com. That figure dwarfs any effect the distance metric could ever have when vectors are normalized. Tuning \(m\) and \(k\) becomes the central accuracy-vs-memory trade-off.

TurboQuant, implemented in Qdrant, improves the state of the art by encoding vectors with a default `bits4` setting and using SIMD-accelerated scoring. It preserves Euclidean structure (inner products and distances) during quantization, so it works equally well with Cosine, Euclidean, or Dot product when vectors are normalized. Its recall stays ahead of binary quantization at equivalent storage budgets, once again illustrating that quantization quality controls the performance ceiling, not the choice of similarity metric.

### Choosing Your Compression Path

If your vectors are not already normalized, normalize them first. Then decide how much memory you can trade for recall.

- **Scalar quantization (int8)**: A safe default. It cuts memory to a quarter with negligible recall impact. Ideal when you are unsure of your workload's sensitivity to quantization loss.
- **Product quantization (m subvectors, k centroids)**: When you need 20 to 100× compression, but accept a measurable recall drop. Start by choosing each subvector to have 8 to 16 dimensions, and \(k=256\) or 512; then benchmark recall and query throughput. Expect to lose roughly a few points of recall for an order-of-magnitude memory saving.
- **TurboQuant / bits4**: When you need the speed of binary-quantization-like compression but better recall. It works out-of-the-box in Qdrant with minimal tuning.

The distance metric debate dissolves once vectors live on the unit hypersphere. The recall, latency, and infrastructure cost of a vector database are overwhelmingly determined by how you quantize and how you set the HNSW search parameters. Spending a day tuning PQ codebook size or swapping an int8 encoder will move your SLA needle in ways a metric switch never will.

---

## Putting It All Together: Architecture Choices and Real-World Tradeoffs

HNSW gives us a graph that jump-starts the search near the right neighbourhood, quantization compresses vectors into memory, and a similarity metric decides proximity. The earlier sections show that metric choice is often nullified by normalization and that quantization errors together with HNSW traversal parameters are the real accuracy levers. This final section connects the pieces into a practical configuration method and production monitoring checklist.

### The Tuning Dials That Actually Move the Needle

Query-time accuracy-versus-latency is controlled primarily by three HNSW parameters, while storage-accuracy is governed by quantization.

*ef_search* sets the beam width during the final layer-0 search. A larger candidate list examines more nodes, raising recall at the cost of CPU time. In practice, doublings of *ef_search* produce steep recall gains until diminishing returns set in. That relationship dwarfs any difference a different distance metric would make on normalized data.

*ef_construction* and *M* determine graph quality at index time. Higher values build a denser graph with more edges per node, letting a given *ef_search* achieve higher recall. The trade-off is increased build time and memory. *M* directly multiplies the per-node storage; doubling *M* roughly doubles index memory. Start with moderate values and profile before turning these knobs.

Quantization applies after indexing. Scalar quantization to int8 delivers a 4× storage reduction with near-zero recall loss. Product quantization splits vectors into subvectors and stores centroid IDs, compressing a 768-dimension float32 vector from 3072 bytes down to 32 bytes (a 96-fold reduction) or even fewer. Aggressive PQ mis-sizing can degrade recall substantially; sweeping subvector count and centroid training is where the largest memory-versus-accuracy wins are made. A high-quality HNSW graph can partially mask PQ errors, but a sloppy PQ setup can wipe out the benefit of a large *ef_search*. The reliable rule: first dial in *ef_search* and quantization, then fine-tune *M* and *ef_construction*.

### When the Metric Actually Matters

We have pushed a strong claim: devoting time to picking cosine similarity over Euclidean distance is, for the vast majority of production vector search workloads, wasted effort. For L2-normalized vectors, the standard output of OpenAI embeddings, Sentence Transformers, and nearly all retrieval models, cosine similarity and Euclidean distance produce identical nearest-neighbour rankings. Under normalization, the squared Euclidean distance between two vectors equals 2 − 2 × cosine similarity. Because the ordering is preserved, a nearest-neighbour search using inner product or Euclidean distance returns the same set of results. A practitioner implementing cosine similarity can safely use Faiss's inner-product index on unit vectors.

The most powerful objection is that unnormalized vectors do exist: raw word2vec embeddings, handcrafted feature vectors where magnitude encodes confidence, or logs where vector norms carry signal. With unnormalized vectors, Euclidean distance can favour a long, dense document over a short, semantically precise query, and cosine similarity is needed to isolate direction from magnitude. The objection is correct in that setting, and if your vectors intentionally preserve magnitude you must select the metric that matches your definition of similarity.

The rebuttal is simple. Modern production pipelines almost universally normalize at ingestion time to decouple magnitude from semantics. Unless you have a deliberate reason to keep magnitude, normalize your vectors and use inner product. This dissolves the metric debate and lets you concentrate on the decisions that genuinely influence recall and latency.

### Flat Index or HNSW?

A brute-force flat index computes the dot product against every vector, guaranteeing perfect recall. For datasets under roughly 100 k items, a tuned BLAS kernel can beat the graph traversal overhead of HNSW while delivering exact results. Beyond that threshold, linear scan cost grows unacceptable. The precise crossover depends on dimensionality and latency target; if an exact search on your dataset stays within twice your latency budget, stay flat. Otherwise, switch to HNSW and tune *ef_search* to meet your SLA, monitoring recall as you go.

### Monitoring Checklist for Production

Once the index is live, these signals keep it healthy.

- **Recall@k**: Measure against a golden query set. A small decline can silently degrade user experience; automate daily checks.
- **Query latency percentiles**: Watch p50, p95, and p99. Rising p99 often means *ef_search* is too small or the index needs tuning.
- **Memory per node**: Track RSS or container memory. A jump may signal an index rebuild with a larger *M* or misconfiguration.
- **Index build time**: For periodically rebuilt indexes, record build duration. Slow builds delay freshness, critical for RAG.
- **Quantization error**: If your system reports reconstruction error, track its trend. An upward drift suggests the current centroid training no longer fits the data, indicating a retrain is due.

Alert on thresholds: recall dropping beneath a floor, p99 latency exceeding the SLA, memory approaching node limits.

### Actionable Takeaways for Senior Engineers

1. Normalize vectors at ingestion and use inner product; this de-fangs the metric dilemma.
2. Choose an HNSW baseline: *M*=16, *ef_construction*=200, *ef_search*=64. Profile recall versus latency and adjust.
3. Apply scalar quantization first; the 4× compression is effectively free. Adopt product quantization only when memory forces it, then sweep subvector size and centroid count while watching recall closely.
4. Stick with a flat index for datasets below roughly 100 k vectors when latency permits exact search; beyond that, move to HNSW with the baseline parameters.
5. Continuously monitor recall@k, latency percentiles, and memory. Tuning parameters post-deployment is far cheaper than a production outage.

The hidden algorithms are not magic; they are a stack of interconnected knobs. Engineers who know which ones actually move the needle are the ones who meet their SLAs at half the infrastructure cost.

---


---

## References

*Ranked by influence on this article (0–100; higher = more influence). Dated where known.*

1. **100** · 2023 · [Similarity Search, Part 4: Hierarchical Navigable Small World ...](https://towardsdatascience.com/similarity-search-part-4-hierarchical-navigable-small-world-hnsw-2aad4fe87d37/)
2. **51** · n.d. · [Quantization - Qdrant](https://qdrant.tech/documentation/manage-data/quantization/)
3. **39** · 2026 · [Implementing Vector Search at Scale: Optimizing HNSW Index ...](https://martinuke0.github.io/posts/2026-05-12-implementing-vector-search-at-scale-optimizing-hnsw-index-construction-for-high-dimensional-embeddings/)
4. **26** · n.d. · [Hierarchical Navigable Small Worlds (HNSW) | Pinecone](https://www.pinecone.io/learn/series/faiss/hnsw/)
5. **22** · n.d. · [Product Quantization: Compressing high-dimensional vectors by 97% | Pinecone](https://www.pinecone.io/learn/series/faiss/product-quantization/)
6. **20** · 2024 · [PDF Survey of vector database management systems](https://dbgroup.cs.tsinghua.edu.cn/ligl/papers/vldbj2024-vectordb.pdf)
7. **20** · 2026 · [HNSW Algorithm Explained: Diagrams + Tuning (2026)](https://krunalkanojiya.com/blog/hnsw-algorithm-explained)
8. **19** · 2026 · [TurboQuant: Online Vector Quantization with Near-optimal Distortion Rate](https://arxiv.org/html/2504.19874v1)
9. **19** · n.d. · [Vector Database Tuning: Index Parameters, Search Configuration, and ...](https://aidev.fit/en/ai/vector-database-tuning.html)
10. **15** · n.d. · [The trade-off between Recall and Latency in HNSW](https://aboutvectordatabase.com/learn/trade-off-between-recall-and-latency-in-hnsw/)
11. **14** · n.d. · [Performance Tuning - HNSW Documentation](https://tfmv.github.io/hnsw/core/performance-tuning/)
12. **11** · 2025 · [Product Quantization for Similarity Search | Towards Data Science](https://towardsdatascience.com/product-quantization-for-similarity-search-2f1f67c5fddd/)
13. **9** · 2025 · [Similarity Search, Part 2: Product Quantization | Towards Data Science](https://towardsdatascience.com/similarity-search-product-quantization-b2a1a6397701/)
14. **8** · n.d. · [The Ultimate Guide to the Vector Database Landscape: 2024 and Beyond](https://www.singlestore.com/blog/-ultimate-guide-vector-database-landscape-2024/)
15. **8** · 2024 · [PDF Vector database management systems: Fundamental concepts, use-cases ...](https://dbs-research.github.io/pdf/2024_vector.pdf)
16. **8** · n.d. · [Vector Database Performance Optimization Guide - Blockchain Council](https://www.blockchain-council.org/ai/vector-database-performance-optimization-recall-latency-cost-indexing-quantization/)
17. **6** · n.d. · [Vector Databases: Architecture Deep Dive | Medium](https://medium.com/@nay1228/unveiling-the-inner-workings-of-vector-databases-a-technical-deep-dive-eac76f0b1779)
18. **6** · n.d. · [HNSW indexing in Vector Databases: Simple explanation and ...](https://medium.com/@wtaisen/hnsw-indexing-in-vector-databases-simple-explanation-and-code-3ef59d9c1920)
19. **5** · n.d. · [Your VectorDB Needs a Tune-Up: HNSW Fine-Tuning Explained](https://medium.com/@keivanipchihagh/your-vectordb-needs-a-tune-up-hnsw-fine-tuning-explained-627a351e230b)
20. **2** · 2024 · [PDF Vector Databases: What's Really New and What's Next? (VLDB 2024 Panel)](https://cs.purdue.edu/homes/csjgwang/pubs/VLDB2024_Panel.pdf)
