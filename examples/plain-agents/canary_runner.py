#!/usr/bin/env python3
"""
Canary Runner - Main entry point for the synthetic canary traffic system.

This script provides a command-line interface for running canary scenarios
to validate the ATLAS observability stack. It supports both mock and real
modes for flexible testing and validation.

Usage:
    python canary_runner.py --config config_mock.yaml
    python canary_runner.py --config config_real.yaml

For more information, see the canary package documentation.
"""

import sys
import argparse
from pathlib import Path

from canary.runner import CanaryRunner


def parse_args():
    """
    Parse command line arguments.

    Returns:
        argparse.Namespace: Parsed arguments
    """
    parser = argparse.ArgumentParser(
        description=(
            "Canary Runner - Synthetic traffic generator for ATLAS "
            "observability validation"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run with mock mode configuration (no API costs)
  python canary_runner.py --config canary/config_mock.yaml

  # Run with real mode configuration (actual API calls)
  python canary_runner.py --config canary/config_real.yaml

  # Run with custom configuration
  python canary_runner.py --config /path/to/custom_config.yaml

Configuration:
  The configuration file should be a YAML file specifying:
  - mode: "mock" or "real"
  - agent: agent_id, agent_name
  - mock_settings: latency and failure rate settings (for mock mode)
  - real_settings: API keys and model settings (for real mode)
  - otlp: OpenTelemetry collector endpoint
  - scenarios: list of scenarios to execute
  - validation: optional telemetry validation settings

Exit Codes:
  0 - All scenarios passed
  1 - One or more scenarios failed or configuration error

For more information, see:
  - canary/RUNNER_USAGE.md
  - canary/config_mock.yaml (example configuration)
  - canary/config_real.yaml (example configuration)
        """
    )

    parser.add_argument(
        "--config",
        type=str,
        required=True,
        help="Path to YAML configuration file"
    )

    return parser.parse_args()


def main():
    """
    Main entry point for the canary runner.

    Parses command line arguments, creates a CanaryRunner instance,
    executes the canary scenarios, and exits with the appropriate status code.

    Returns:
        int: Exit code (0 for success, 1 for failure)
    """
    # Parse command line arguments
    args = parse_args()

    # Validate configuration file exists
    config_path = Path(args.config)
    if not config_path.exists():
        print(f"Error: Configuration file not found: {args.config}")
        print(f"Please provide a valid configuration file path.")
        return 1

    # Print banner
    print("=" * 60)
    print("ATLAS Canary Runner")
    print("Synthetic Traffic Generator for Observability Validation")
    print("=" * 60)

    # Create and run canary runner
    try:
        runner = CanaryRunner(str(config_path))
        exit_code = runner.run()
        return exit_code
    except KeyboardInterrupt:
        print("\n\nCanary execution interrupted by user")
        return 1
    except Exception as e:
        print(f"\n\nUnexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
