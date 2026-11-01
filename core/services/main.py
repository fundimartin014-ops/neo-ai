import asyncio
from core.services.ollama_service import ask_ollama


async def main():
    print("Neo Async Started")

    while True:
        user_input = input("You: ")

        if user_input.lower() == "exit":
            break

        response = await ask_ollama(user_input)

        print(f"Neo: {response}")


if __name__ == "__main__":
    asyncio.run(main())
