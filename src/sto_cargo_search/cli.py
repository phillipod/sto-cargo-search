"""
Script to search and display formatted information from Star Trek Online (STO) cargo JSON files.
Supports logical search expressions and formats data into tables or detailed views.
"""

import json
import argparse
import re
import html
import time
import requests
import os
from pathlib import Path
from datetime import datetime, timedelta
from prettytable import PrettyTable
from pyparsing import infixNotation, opAssoc, Word, QuotedString, alphanums, ParserElement, ParseException
from html.parser import HTMLParser

ParserElement.enablePackrat()

# === Constants for Cargo Downloading ===
WIKI_BASE_URL = "https://stowiki.net/wiki/"
CARGO_EXPORT_PAGE = "Special:CargoExport"
DEFAULT_CACHE_DIR = Path(os.path.expanduser('~')) / '.sto-cargo-cache'
CACHE_EXPIRE_DAYS = 3

CARGO_TYPES = {
    'equipment': {
        'tables': 'Infobox',
        'fields': '_pageName=Page,name,rarity,type,boundto,boundwhen,who,' + ','.join(f'{prefix}{i}' for prefix in ('head', 'subhead', 'text') for i in range(1,10)),
        'limit': 5000,
    },
    'personal_trait': {
        'tables': 'Traits',
        'fields': '_pageName=Page,name,chartype,environment,type,isunique,description',
        'limit': 2500,
    },
    'starship_trait': {
        'tables': 'StarshipTraits',
        'fields': '_pageName=Page,name,short,type,detailed,obtained,basic',
        'limit': 2500,
        'where': 'name IS NOT NULL',
    },
    'doff': {
        'tables': 'Specializations',
        'fields': '_pageName=Page,name=doff_specialization,shipdutytype,department,description,white,green,blue,purple,violet,gold',
        'limit': 1000,
    },
}

class CargoDownloader:
    def __init__(self, force_download=False, cache_dir=DEFAULT_CACHE_DIR):
        self.force_download = force_download
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        print(f"Using cache directory: {self.cache_dir}")
        print()

    def build_url(self, cargo_type, offset=0):
        conf = CARGO_TYPES[cargo_type]
        params = [
            f"tables={conf['tables']}",
            f"fields={conf['fields']}",
            f"limit={conf['limit']}",
            f"offset={offset}",
            "format=json",
        ]
        if 'where' in conf:
            params.append(f"where={conf['where']}")
        return WIKI_BASE_URL + CARGO_EXPORT_PAGE + "?" + "&".join(params)

    def cache_file(self, cargo_type):
        return self.cache_dir / f"{cargo_type}.json"

    def is_cache_valid(self, path):
        if not path.exists():
            return False
        return datetime.fromtimestamp(path.stat().st_mtime) > datetime.now() - timedelta(days=CACHE_EXPIRE_DAYS)

    def download_all(self):
        for cargo_type in CARGO_TYPES:
            self.download(cargo_type)

    def download(self, cargo_type):
        path = self.cache_file(cargo_type)
        if not self.force_download and self.is_cache_valid(path):
            return

        print(f"Downloading {cargo_type} data...")
        all_data = []
        offset = 0
        while True:
            url = self.build_url(cargo_type, offset)
            response = requests.get(url)
            if not response.ok:
                print(f"Failed to download {cargo_type} at offset {offset}")
                break

            batch = response.json()
            if not batch:
                break

            all_data.extend(batch)

            if len(batch) < CARGO_TYPES[cargo_type]['limit']:
                break

            offset += CARGO_TYPES[cargo_type]['limit']
            time.sleep(1)  # Be polite to the server

        with open(path, 'w', encoding='utf-8') as f:
            json.dump(all_data, f, ensure_ascii=False, indent=2)

    def load(self, cargo_type):
        path = self.cache_file(cargo_type)
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)

class HTMLStripper(HTMLParser):
    """Utility class to strip HTML tags from text."""
    def __init__(self):
        super().__init__()
        self.result = []

    def handle_data(self, d):
        self.result.append(d)

    def get_data(self):
        return ''.join(self.result)

def strip_html_tags(text):
    """Removes HTML tags and unescapes HTML entities from a string."""
    text = html.unescape(text)
    text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
    stripper = HTMLStripper()
    stripper.feed(text)
    return stripper.get_data()

class SearchTerm:
    """Represents a single keyword term in a search expression."""
    def __init__(self, tokens):
        self.term = tokens[0]

    def evaluate(self, obj):
        for key, value in obj.items():
            if value is not None and self.term.lower() in str(value).lower():
                return True
        return False

class BinaryOperation:
    """Handles AND and OR operations in the search expression."""
    def __init__(self, tokens):
        self.operator = tokens[0][1].lower()
        self.operands = tokens[0][0::2]

    def evaluate(self, obj):
        if self.operator == 'and':
            return all(op.evaluate(obj) for op in self.operands)
        elif self.operator == 'or':
            return any(op.evaluate(obj) for op in self.operands)

class NotOperation:
    """Handles NOT operation in the search expression."""
    def __init__(self, tokens):
        self.operand = tokens[0][1]

    def evaluate(self, obj):
        return not self.operand.evaluate(obj)

def load_json_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)

def parse_search_expression(expr):
    expr = expr.replace(',', ' OR')
    expr = re.sub(r'\bAND\b', 'and', expr, flags=re.IGNORECASE)
    expr = re.sub(r'\bOR\b', 'or', expr, flags=re.IGNORECASE)
    expr = re.sub(r'\bNOT\b', 'not', expr, flags=re.IGNORECASE)
    term = QuotedString('"') | Word(alphanums + '-_')
    term.setParseAction(SearchTerm)
    search_expr = infixNotation(term,
        [
            ('not', 1, opAssoc.RIGHT, NotOperation),
            ('and', 2, opAssoc.LEFT, BinaryOperation),
            ('or',  2, opAssoc.LEFT, BinaryOperation),
        ])
    try:
        return search_expr.parseString(expr, parseAll=True)[0]
    except ParseException as e:
        print(f"Error parsing search expression: {e}")
        exit(1)

def format_text_with_indent(text, indent_level, strip_html=True):
    if strip_html:
        text = strip_html_tags(text)
    lines = text.split('\n')
    formatted_lines = []
    for line in lines:
        if ':' in line:
            parts = line.split(':', 1)
            formatted_lines.append('\t' * indent_level + parts[0].strip())
            formatted_lines[-1] += '\t' + parts[1].strip()
        else:
            formatted_lines.append('\t' * indent_level + line.strip())
    return '\n'.join(formatted_lines)

def detect_format(obj):
    if 'doff_specialization' in obj:
        return 'doff'
    elif 'basic' in obj or 'detailed' in obj or 'obtained' in obj:
        return 'starship_trait'
    elif 'chartype' in obj and 'environment' in obj:
        return 'personal_trait'
    elif any(k.startswith('head') or k.startswith('text') or k.startswith('subhead') for k in obj.keys()):
        return 'equipment'
    return 'unknown'

def print_equipment(obj, strip_html):
    for key in ["name", "rarity", "type"]:
        if key in obj:
            print(f"{key.capitalize()}: {obj[key]}")
    print()
    pattern = re.compile(r'^(head|subhead|text)(\d+)$', re.IGNORECASE)
    fields = {}
    for key, value in obj.items():
        if value is not None:
            match = pattern.match(key)
            if match:
                group, number = match.groups()
                number = int(number)
                fields.setdefault(number, {})[group.lower()] = value
    for num in sorted(fields):
        section = fields[num]
        head = section.get('head')
        subhead = section.get('subhead')
        text = section.get('text')
        if head:
            print(f"{head}")
        if subhead and head:
            print(f"\t{subhead}")
        elif subhead:
            print(f"{subhead}")
        if text:
            indent = 0
            if subhead:
                indent = 2
            elif head:
                indent = 1
            print(format_text_with_indent(text, indent, strip_html))
    print("\n" + "-"*40 + "\n")

def print_starship_trait(obj, strip_html):
    print(f"Name: {obj.get('name', '')}")
    print(f"Type: {obj.get('type', '')}")
    print(f"Short: {obj.get('short', '')}\n")
    if obj.get('basic'):
        print("Basic:")
        print(format_text_with_indent(obj['basic'], 1, strip_html))
    if obj.get('detailed'):
        print("\nDetailed:")
        print(format_text_with_indent(obj['detailed'], 1, strip_html))
    if obj.get('obtained'):
        print("\nObtained:")
        print(format_text_with_indent(obj['obtained'], 1, strip_html))
    print("\n" + "-"*40 + "\n")

def print_doff(obj, strip_html):
    print(f"Specization: {obj.get('doff_specialization', '')}")
    print(f"Ship Duty: {obj.get('shipdutytype', '')}")
    print(f"Department: {obj.get('department', '')}\n")
    if obj.get('description'):
        print("Description:")
        print(format_text_with_indent(obj['description'], 1, strip_html))
    for tier in ['white', 'green', 'blue', 'purple', 'violet', 'gold']:
        if obj.get(tier):
            print(f"\n{tier.capitalize()}:")
            print(format_text_with_indent(obj[tier], 1, strip_html))
    print("\n" + "-"*40 + "\n")

def print_personal_trait(obj, strip_html):
    print(f"Name: {obj.get('name', '')}")
    print(f"Type: {obj.get('type', '')}")
    print(f"Environment: {obj.get('environment', '')}")
    print(f"Character Type: {obj.get('chartype', '')}")
    print(f"Unique: {'Yes' if obj.get('isunique') else 'No'}\n")
    if obj.get('description'):
        print("Description:")
        print(format_text_with_indent(obj['description'], 1, strip_html))
    print("\n" + "-"*40 + "\n")

def main():
    parser = argparse.ArgumentParser(description='Search STO cargo files and display content.', formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument('--file', help='Path to a specific JSON file')
    parser.add_argument('--search-type', type=lambda s: s.split(','), help=f"""\
Comma-separated list of data types to search. 
Valid types: {' '.join(sorted(CARGO_TYPES.keys()))}
If not specified, all types will be searched."""
    )
    parser.add_argument('--search', help='Search expression')
    parser.add_argument('--list-all', action='store_true', help='List all entries')
    parser.add_argument('--full', action='store_true', help='Display full details')
    parser.add_argument('--no-strip-html', action='store_true', help='Do not strip HTML tags')
    parser.add_argument('--force-download', action='store_true', help='Force redownload of cargo data')
    parser.add_argument('--cache-dir', type=str, help='Override the default cache directory')
    args = parser.parse_args()

    if args.search and args.list_all:
        print("Error: --search and --list-all are mutually exclusive.")
        parser.print_help()
        exit(1)
        
    if not (args.search or args.list_all or args.force_download):
        print("Error: You must specify at least one of --search, --list-all, or --force-download.")
        parser.print_help()
        exit(1)
        
    cache_dir = Path(args.cache_dir).expanduser() if args.cache_dir else DEFAULT_CACHE_DIR

    if args.force_download and not (args.search or args.list_all):
        downloader = CargoDownloader(force_download=True, cache_dir=cache_dir)
        downloader.download_all()
        print("Download complete.")
        return

    downloader = CargoDownloader(force_download=args.force_download, cache_dir=cache_dir)
    downloader.download_all()

    default_files = {
        'equipment': downloader.cache_file('equipment'),
        'starship_trait': downloader.cache_file('starship_trait'),
        'doff': downloader.cache_file('doff'),
        'personal_trait': downloader.cache_file('personal_trait')
    }

    selected_types = args.search_type if args.search_type else list(CARGO_TYPES.keys())
    selected_types = set(selected_types) & set(CARGO_TYPES.keys())

    if not selected_types:
        print("Error: No valid search types selected.")
        parser.print_help()
        exit(1)
        
    all_matches = {'equipment': [], 'starship_trait': [], 'doff': [], 'personal_trait': []}

    if args.file:
        if not Path(args.file).exists():
            print(f"File not found: {args.file}")
            return
        try:
            data = load_json_file(args.file)
        except json.JSONDecodeError as e:
            print(f"Error loading JSON: {e}")
            return
        if not isinstance(data, list):
            print("JSON data must be a list of objects.")
            return
        inferred_type = detect_format(data[0])
        if args.search_type and args.search_type != inferred_type:
            print(f"Error: File format is '{inferred_type}', but --search-type was set to '{args.search_type}'.")
            return
        search_tree = parse_search_expression(args.search) if args.search else None
        seen = set()
        for obj in data:
            identifier = obj.get('name') or obj.get('doff_specialization') or obj.get('_pageName')
            if identifier and identifier not in seen:
                if not search_tree or search_tree.evaluate(obj):
                    all_matches[inferred_type].append(obj)
                    seen.add(identifier)
    else:
        for stype in selected_types:
            filename = default_files.get(stype)
            if not filename or not Path(filename).exists():
                continue
            try:
                data = load_json_file(filename)
            except json.JSONDecodeError:
                continue
            if not isinstance(data, list):
                continue
            search_tree = parse_search_expression(args.search) if args.search else None
            seen = set()
            for obj in data:
                identifier = obj.get('name') or obj.get('doff_specialization') or obj.get('_pageName')
                if identifier and identifier not in seen:
                    if not search_tree or search_tree.evaluate(obj):
                        all_matches[stype].append(obj)
                        seen.add(identifier)

    strip_html = not args.no_strip_html

    printed_header = False
    if args.full:
        for fmt, items in all_matches.items():
            if items:
                if printed_header:
                    print()
                    
                print(f"=== {fmt.replace('_', ' ').upper()} MATCHES ===\n")
                printed_header = True

                for obj in items:
                    if fmt == 'starship_trait':
                        print_starship_trait(obj, strip_html)
                    elif fmt == 'doff':
                        print_doff(obj, strip_html)
                    elif fmt == 'equipment':
                        print_equipment(obj, strip_html)
                    elif fmt == 'personal_trait':
                        print_personal_trait(obj, strip_html)
    else:
        for fmt, items in all_matches.items():
            if items:
                if printed_header:
                    print()
                    
                print(f"=== {fmt.replace('_', ' ').upper()} MATCHES ===\n")
                printed_header = True

                table = PrettyTable()
                if fmt == 'starship_trait':
                    table.field_names = ["Type", "Name", "Short"]
                    for obj in items:
                        table.add_row([obj.get('type', ''), obj.get('name', ''), obj.get('short', '')])
                elif fmt == 'doff':
                    table.field_names = ["DOff Specialization", "Ship Duty", "Department", "Description"]
                    for obj in items:
                        table.add_row([obj.get('doff_specialization', ''), obj.get('shipdutytype', ''), obj.get('department', ''), strip_html_tags(obj.get('description', '') or '')])
                elif fmt == 'equipment':
                    table.field_names = ["Type", "Name", "Rarity"]
                    for obj in items:
                        table.add_row([obj.get('type', ''), obj.get('name', ''), obj.get('rarity', '')])
                elif fmt == 'personal_trait':
                    table.field_names = ["Name", "Type", "Environment", "Unique"]
                    for obj in items:
                        table.add_row([
                            obj.get('name', ''),
                            obj.get('type', ''),
                            obj.get('environment', ''),
                            'Yes' if obj.get('isunique') else 'No'
                        ])
                print(table)

if __name__ == '__main__':
    main()