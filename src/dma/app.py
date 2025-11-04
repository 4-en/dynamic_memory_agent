# main entry point for the DMA application
# includes initialization and startup logic
# with module selection based on arguments

import argparse
import sys

def launch_web():
    # get port, ip, debug from args
    parser = argparse.ArgumentParser(description="Launch DMA Web Server")
    parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
    )
    parser.add_argument(
        "--debug",
        action="store_true",
    )
    args = parser.parse_args()
    print(f"Starting web server on {args.host}:{args.port} (debug={args.debug})")
    

def launch_cli():
    parser = argparse.ArgumentParser(description="Launch DMA CLI")
    parser.add_argument(
        "--config",
        type=str,
        default="config.yaml",
    )
    args = parser.parse_args()
    print(f"Starting CLI with config: {args.config}")

def launch_build_memory():
    parser = argparse.ArgumentParser(description="Launch DMA Memory Builder")
    parser.add_argument(
        "--type",
        type=str,
        choices=["wikipedia", "mediawiki", "directory"],
        required=True,
        help="Type of memory to build"
    )
    parser.add_argument(
        "--category",
        type=str,
        help="Root category for Wikipedia/MediaWiki crawl"
    )
    parser.add_argument(
        "--path",
        type=str,
        help="Path for directory memory"
    )
    args = parser.parse_args()
    print(f"Building memory of type: {args.type}")
    if args.type in ["wikipedia", "mediawiki"]:
        print(f"Using root category: {args.category}")
    elif args.type == "directory":
        print(f"Using directory path: {args.path}")

def launch():
    # 1. parse module, ie web api, cli, build-memory, with web as default
    # then let each module handle its own args
    parser = argparse.ArgumentParser(description="DMA Launcher")
    parser.add_argument(
        "--module",
        type=str,
        choices=["web", "cli", "build-memory"],
        default="web",
        help="Module to launch: web (default), cli, build-memory"
    )
    args, unknown = parser.parse_known_args()
    module = args.module
    
    match module:
        case "web":
            launch_web()
        case "cli":
            launch_cli()
        case "build-memory":
            launch_build_memory()
        case _:
            print(f"Unknown module: {module}")
            sys.exit(1)
            
if __name__ == "__main__":
    launch()
    