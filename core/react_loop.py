# core/react_loop.py
async def react_loop(user_input, max_iterations=5):
    context = MemoryManager.retrieve(user_input)
    thought_history = []
    
    for i in range(max_iterations):
        # THINK
        thought = await groq_llm.generate(
            f"User: {user_input}\n"
            f"Context: {context}\n"
            f"History: {thought_history}\n"
            f"What should I do next? (search_memory|use_tool|answer)"
        )
        
        if thought.action == "answer":
            return await generate_final_answer(thought, context)
        
        elif thought.action == "use_tool":
            result = await execute_tool(thought.tool_name, thought.parameters)
            thought_history.append({"tool": thought.tool_name, "result": result})
            context += f"\n[Tool result]: {result}"
    
    return await generate_final_answer("Max iterations reached", context)