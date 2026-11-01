import tkinter as tk

import requests

API = "http://127.0.0.1:8000/ask"


def ask_neo(entry, output):
    query = entry.get()
    if not query:
        return
    response = requests.post(API, json={"query": query}, timeout=15).json()
    output.insert(tk.END, "Neo: " + response.get("answer", "") + "\n")


def create_app():
    root = tk.Tk()
    root.title("Neo AI Assistant")

    entry = tk.Entry(root, width=50)
    entry.pack()

    btn = tk.Button(root, text="Ask Neo", command=lambda: ask_neo(entry, output))
    btn.pack()

    output = tk.Text(root, height=15, width=60)
    output.pack()

    return root


def main():
    create_app().mainloop()


if __name__ == "__main__":
    main()
