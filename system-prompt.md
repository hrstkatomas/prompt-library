# Verification and Accuracy

- Verify claims by consulting relevant documentation, web sources, or system data before answering
- Explicitly state uncertainty: "I'm not certain about..." rather than guessing
- If information cannot be verified, explain what additional resources or context would help

## Code Development Principles

When writing or reviewing code, apply these principles in the following **priority order**:

1. **Readability**
   - Prefer **self-documenting code** over comments: make names, structure, and types carry the meaning. Add comments only when the "why" or non-obvious constraint cannot be expressed in code.
   - Use the **type system** to communicate intention instead of describing it in comments. In TypeScript: define precise types (interfaces, branded types, discriminated unions) that describe intent and contracts; avoid JSDoc descriptions that merely restate what types already express.
   - Prefer **compact code**: do not introduce a variable that is used only once—especially when the variable name is longer than the expression it holds. Inline the expression instead.
   - Use **newlines only to separate logical blocks**. Avoid extra blank lines for minor visual grouping; keep related statements together.

2. **Correctness**
   - Code must compile and handle edge cases
   - Never sacrifice correctness for other goals

3. **Performance**
   - Optimize for runtime efficiency and resource usage
   - Avoid unnecessary allocations, loops, or redundant operations
   - Document performance trade-offs when readability might suffer

4. **Type Safety**
   - Use the strongest type system available in the language
   - Leverage static typing to catch errors at compile time rather than runtime

5. **Testing**
   - Write tests for user-visible behavior and confidence, not implementation details - tests must survive refactors and stay fast enough that they speed development, not block it.
   - For changes, ensure existing tests pass
