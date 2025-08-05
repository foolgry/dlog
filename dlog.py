#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import subprocess
import argparse
import sys
import re
import os
from configparser import ConfigParser
from pathlib import Path

# --- Configuration ---
# 使用脚本所在目录的 dlog.conf 文件
SCRIPT_DIR = Path(__file__).parent.resolve()
CONFIG_FILE = SCRIPT_DIR / "dlog.conf"
COLOR_YELLOW = '\033[93m'
COLOR_RED = '\033[91m'
COLOR_RESET = '\033[0m'

def get_ssh_target(ssh_target_arg: str = None) -> str:
    """
    Determines the SSH target.
    Priority: 1. Command-line argument -> 2. Config file -> 3. Error
    """
    if ssh_target_arg:
        return ssh_target_arg

    if CONFIG_FILE.exists():
        parser = ConfigParser()
        parser.read(CONFIG_FILE)
        try:
            return parser.get('default', 'target')
        except (KeyError, ValueError):
            pass # Fall through if config is malformed or key is missing

    print(f"{COLOR_RED}Error: SSH target not specified.{COLOR_RESET}", file=sys.stderr)
    print("Please provide it as the first argument, or set a default in the config file.", file=sys.stderr)
    print(f"Example CLI: dlog user@host my-service ERROR", file=sys.stderr)
    print(f"Example config (~/.config/dlog/config):\n[default]\ntarget = user@host", file=sys.stderr)
    sys.exit(1)

def find_service_name(ssh_target: str, partial_name: str) -> str:
    """
    Finds the full service name on the REMOTE Docker Swarm.
    """
    # The Docker command is now wrapped in an ssh command
    docker_cmd = f"docker service ls --format '{{{{.Name}}}}'"
    ssh_cmd = ['ssh', ssh_target, docker_cmd]
    
    try:
        result = subprocess.check_output(ssh_cmd, text=True, stderr=subprocess.PIPE)
        service_names = result.strip().split('\n')
        
        matches = [name for name in service_names if partial_name in name]

        if len(matches) == 0:
            print(f"Error: No service found matching '{partial_name}' on host {ssh_target}.", file=sys.stderr)
            sys.exit(1)
            
        if len(matches) > 1:
            print(f"Error: Ambiguous service name '{partial_name}'. Found matches: {matches}", file=sys.stderr)
            sys.exit(1)

        return matches[0]

    except subprocess.CalledProcessError as e:
        print(f"Error executing command on remote host '{ssh_target}':\n{e.stderr}", file=sys.stderr)
        sys.exit(1)
    except FileNotFoundError:
        print("Error: 'ssh' command not found. Is it installed and in your PATH?", file=sys.stderr)
        sys.exit(1)

def stream_logs(ssh_target: str, service_name: str, keyword: str = None, lines: int = 100, follow: bool = False, ignore_case: bool = False):
    """
    Streams and filters logs from the remote service.
    """
    docker_command_parts = ['docker', 'service', 'logs', '--raw']
    if follow:
        docker_command_parts.append('-f')
        docker_command_parts.extend(['--tail', str(lines) if lines else '10'])
    elif lines:
        docker_command_parts.extend(['--tail', str(lines)])
    docker_command_parts.append(service_name)
    
    # Join the docker command parts into a single string to be executed by ssh
    docker_command_str = " ".join(docker_command_parts)
    
    # The final command to run locally
    ssh_command = ['ssh', ssh_target, docker_command_str]

    try:
        process = subprocess.Popen(ssh_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8')

        regex_flags = re.IGNORECASE if ignore_case else 0
        # 日期行的正则表达式
        date_pattern = re.compile(r'^\d{4}-\d{2}-\d{2}')
        
        # 缓存上一行，用于处理多行日志
        previous_line = ""
        previous_line_matches = False

        for line in iter(process.stdout.readline, ''):
            # 判断当前行是否是新的日志条目（以日期开头）
            is_new_log_entry = bool(date_pattern.match(line))
            
            if not keyword:
                print(line, end='')
                continue

            # 如果是新日志条目，处理上一行
            if is_new_log_entry and previous_line:
                if previous_line_matches:
                    # 对匹配的行进行高亮处理
                    highlighted_line = re.sub(
                        f'({re.escape(keyword)})',
                        f'{COLOR_YELLOW}\\1{COLOR_RESET}',
                        previous_line,
                        flags=regex_flags
                    )
                    print(highlighted_line, end='')
                previous_line = ""
                previous_line_matches = False

            # 检查当前行是否匹配关键词
            current_line_matches = bool(re.search(keyword, line, regex_flags))
            
            if is_new_log_entry:
                # 新日志条目
                previous_line = line
                previous_line_matches = current_line_matches
            else:
                # 延续上一行的日志（如堆栈信息）
                if previous_line_matches or current_line_matches:
                    # 如果上一行匹配或者当前行匹配，则保留上一行并添加当前行
                    if previous_line:
                        # 只有当有上一行时才打印，并进行高亮处理
                        highlighted_line = re.sub(
                            f'({re.escape(keyword)})',
                            f'{COLOR_YELLOW}\\1{COLOR_RESET}',
                            previous_line,
                            flags=regex_flags
                        )
                        print(highlighted_line, end='')
                        previous_line = ""
                    # 对当前行进行高亮处理
                    highlighted_line = re.sub(
                        f'({re.escape(keyword)})',
                        f'{COLOR_YELLOW}\\1{COLOR_RESET}',
                        line,
                        flags=regex_flags
                    )
                    print(highlighted_line, end='')
                    previous_line_matches = True  # 标记为匹配，以便后续行也能打印
        
        # 处理最后缓存的一行
        if previous_line and previous_line_matches:
            # 对最后匹配的行进行高亮处理
            highlighted_line = re.sub(
                f'({re.escape(keyword)})',
                f'{COLOR_YELLOW}\\1{COLOR_RESET}',
                previous_line,
                flags=regex_flags
            )
            print(highlighted_line, end='')
        
        _, stderr = process.communicate()
        if process.returncode != 0:
            # Don't print stderr on clean Ctrl+C exit
            if "Killed by signal" not in stderr and process.returncode != 130:
                 print(f"Error streaming logs from {service_name}:\n{stderr}", file=sys.stderr)

    except KeyboardInterrupt:
        print("\nExiting log stream.")
        process.terminate()
    except Exception as e:
        print(f"An unexpected error occurred: {e}", file=sys.stderr)

def main():
    parser = argparse.ArgumentParser(
        description="A local CLI tool to search logs for a Docker Swarm service on a remote host.",
        epilog="Example: dlog my-api ERROR -n 200 -i"
    )
    # The first argument is now optional; we can get it from the config file
    parser.add_argument('target_or_service', help='SSH target (user@host) OR service name if target is in config.')
    parser.add_argument('service_or_keyword', nargs='?', help='Service name OR keyword (if service is from config).')
    parser.add_argument('keyword', nargs='?', default=None, help='Keyword to search for. (optional)')
    parser.add_argument('-n', '--lines', type=int, default=100, help='Number of recent lines to show. (default: 100)')
    parser.add_argument('-f', '--follow', action='store_true', help='Follow log output in real-time.')
    parser.add_argument('-i', '--ignore-case', action='store_true', help='Perform a case-insensitive search.')

    args = parser.parse_args()

    ssh_target = None
    service = None
    keyword = None

    # This logic allows for flexible arguments:
    # dlog user@host service keyword
    # dlog service keyword (reads user@host from config)
    if '@' in args.target_or_service:
        ssh_target = args.target_or_service
        service = args.service_or_keyword
        keyword = args.keyword
    else:
        ssh_target = get_ssh_target() # Tries to read from config
        service = args.target_or_service
        keyword = args.service_or_keyword

    if not service:
        parser.error("The service name is required.")

    full_service_name = find_service_name(ssh_target, service)
    print(f"--- Streaming logs for service: {COLOR_YELLOW}{full_service_name}{COLOR_RESET} on host: {COLOR_YELLOW}{ssh_target}{COLOR_RESET} ---")
    
    stream_logs(ssh_target, full_service_name, keyword, args.lines, args.follow, args.ignore_case)

if __name__ == "__main__":
    main()
