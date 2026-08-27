"""Debug helper: runs the router on a question from the CLI.

The full ReAct trace is saved automatically by graph.ask() (see
utils.save_run_trace) under runs/<timestamp>/, no extra step needed here.

Usage: python debug_run.py "sua pergunta aqui"
"""
import sys

from graph import ask

if __name__ == "__main__":
    pergunta = sys.argv[1] if len(sys.argv) > 1 else "Quantos treinos eu fiz em agosto de 2026?"
    resultado = ask(pergunta)
    print(resultado["answer"])
    if resultado["artifact_url"]:
        print("artifact_url:", resultado["artifact_url"])
