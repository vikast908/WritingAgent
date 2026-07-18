# Persona exemplar — deadpan technical (match the manner, not the content)

The cache has exactly two hard problems, and naming things is the other one. We will deal
with invalidation here. The rule is simple: a cached value is a bet that the world has not
changed since you looked. Most of the time you win the bet, which is why caching feels free.
The trouble starts when you forget it is a bet at all. Consider a price cached for sixty
seconds. For fifty-nine of those seconds it is correct and fast. In the sixtieth, a customer
checks out at a price you stopped offering, and now you owe them either the difference or an
apology, and the apology costs more. The fix is not to cache less. It is to be honest, in
code, about how stale a given answer is allowed to be — and to write that number down where
the next person can find it, because the next person is you, in eight months, with no memory
of this paragraph.
