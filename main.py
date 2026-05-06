"""
Kafka Health Monitor — point d'entrée principal.

Usage :
    python main.py --mode cli status          # snapshot instantané
    python main.py --mode cli watch           # surveillance continue
    python main.py --mode cli history -g mon-groupe -t mon-topic
    python main.py --mode web                 # dashboard sur http://localhost:8080
"""
import argparse
import sys


def main():
    parser = argparse.ArgumentParser(
        description="Kafka Health Monitor — CLI et Dashboard Web",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples :
  python main.py --mode cli status
  python main.py --mode cli watch --interval 10
  python main.py --mode cli history --group my-app --topic orders --hours 2
  python main.py --mode web
        """
    )
    parser.add_argument(
        "--mode",
        choices=["cli", "web"],
        default="cli",
        help="Interface à utiliser (défaut : cli)"
    )

    # On parse seulement --mode ici, le reste est laissé à Click (CLI)
    args, remaining = parser.parse_known_args()

    if args.mode == "web":
        from interfaces.web import run_web
        run_web()
    else:
        # Passe les arguments restants à Click
        sys.argv = [sys.argv[0]] + remaining
        from interfaces.cli import cli
        cli()


if __name__ == "__main__":
    main()
