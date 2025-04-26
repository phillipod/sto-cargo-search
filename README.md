# STO Cargo Search

## Description

**STO Cargo Search** is a command-line tool designed to search cargo data for the popular online game Star Trek Online (STO). It retrieves and parses JSON cargo files obtained from the unofficial [stowiki.net](https://stowiki.net) wiki. The tool includes robust searching and listing capabilities to easily query various types of data including personal traits, starship traits, duty officers (DOFFs), and equipment.

## Installation

Install STO Cargo Search easily via pip:

```bash
pip install .
```

Alternatively, install directly from a repository:

```bash
pip install git+https://github.com/phillipod/sto-cargo-search.git
```

Make sure Python 3.7 or later is installed on your system.

## Usage

Basic command structure:

```bash
sto-cargo-search [options]
```

### Options

- `--file FILE`: Path to a specific JSON file. Overrides the `--search-type` parameter if provided.
- `--search-type SEARCH_TYPE`: Comma-separated list of cargo data types to search within.
  
  Valid types: `doff`, `equipment`, `personal_trait`, `starship_trait`.  
  If not specified, all types will be searched.
- `--search SEARCH`: Search expression to filter results.
- `--list-all`: Lists all available entries; mutually exclusive with `--search`.
- `--full`: Displays full details for each match.
- `--no-strip-html`: Preserves HTML tags in output.
- `--force-download`: Forces redownload of cargo data, bypassing the default 3-day cache.
- `--cache-dir CACHE_DIR`: Customizes the cache directory for storing downloaded cargo data.

### Important Notes

- **Caching Behavior**: By default, the tool caches downloaded cargo data for three days to reduce unnecessary network traffic. Use `--force-download` to override this behavior.
- **Parameter Precedence**: When `--file` is provided, it overrides any specified `--search-type`.
- **Mutually Exclusive**: The options `--list-all` and `--search` cannot be used simultaneously.

## Examples

### Displaying Help

```bash
sto-cargo-search --help
```

### Search by Traits

```bash
sto-cargo-search --search "\"fire at will\"" --search-type personal_trait,starship_trait,doff
```

### Specific Search with Logic

```bash
sto-cargo-search --search "\"exotic damage\" and (hangar or craft or allies or allied or pets)"
```

### Full Detail Search

```bash
sto-cargo-search --search "gemini" --full
```

## Dependencies

- `requests`
- `prettytable`
- `pyparsing`

## License

This project is licensed under the GNU General Public License v3 (GPL3).

## Contact

For further information or support, please refer to the project maintainer listed in the project's `pyproject.toml` file.
