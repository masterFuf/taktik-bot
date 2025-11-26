"""
Taktik Automation CLI
=====================

Point d'entrée CLI pour l'automatisation programmatique.

Usage:
    python -m taktik.core.automation --config config.json
    python -m taktik.core.automation --config config.json --dry-run
    python -m taktik.core.automation --generate-example
"""

import sys
import argparse
from pathlib import Path
from loguru import logger

from .session_runner import SessionRunner
from .config_loader import ConfigLoader


def setup_logging(verbose: bool = False):
    """Configure le logging"""
    logger.remove()
    
    level = "DEBUG" if verbose else "INFO"
    
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
        level=level
    )


def generate_example_config(output_path: str, platform: str = "instagram"):
    """Génère un fichier de config d'exemple"""
    config = ConfigLoader.create_example_config(platform)
    ConfigLoader.to_json(config, output_path)
    
    print(f"✅ Example config generated: {output_path}")
    print(f"\n📝 Edit the file and replace:")
    print(f"   - your_username → Your {platform} username")
    print(f"   - your_password → Your {platform} password")
    print(f"   - emulator-5566 → Your device ID (adb devices)")
    print(f"   - tk_live_your_api_key_here → Your Taktik API key")
    print(f"\n🚀 Then run:")
    print(f"   python -m taktik.core.automation --config {output_path}")


def run_session(config_path: str, dry_run: bool = False):
    """Exécute une session"""
    try:
        # Charger la config
        runner = SessionRunner.from_config(config_path)
        
        print(f"\n{'='*60}")
        print(f"🚀 TAKTIK AUTOMATION SESSION")
        print(f"{'='*60}")
        print(f"Session ID: {runner.session_id}")
        print(f"Platform:   {runner.config.platform}")
        print(f"Username:   @{runner.config.account.username}")
        print(f"Device:     {runner.config.device_id}")
        print(f"Workflow:   {runner.config.workflow.type}")
        
        if runner.config.workflow.target_type:
            print(f"Target:     {runner.config.workflow.target_type}")
            if runner.config.workflow.hashtag:
                print(f"Hashtag:    #{runner.config.workflow.hashtag}")
        
        print(f"{'='*60}\n")
        
        if dry_run:
            print("🔍 DRY RUN MODE - Configuration validated, not executing")
            return
        
        # Exécuter
        result = runner.execute()
        
        # Afficher le résumé
        print(f"\n{result.summary()}")
        
        # Sauvegarder le résultat
        result_path = Path(config_path).parent / f"result_{runner.session_id}.json"
        import json
        with open(result_path, 'w', encoding='utf-8') as f:
            json.dump(result.to_dict(), f, indent=2, ensure_ascii=False)
        
        print(f"\n💾 Result saved: {result_path}")
        
        # Code de sortie
        if result.status.value == "success":
            sys.exit(0)
        else:
            sys.exit(1)
        
    except FileNotFoundError as e:
        logger.error(f"❌ Config file not found: {e}")
        sys.exit(1)
    except ValueError as e:
        logger.error(f"❌ Invalid configuration: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}")
        sys.exit(1)


def main():
    """Point d'entrée principal"""
    parser = argparse.ArgumentParser(
        description="Taktik Automation - Programmatic Instagram/TikTok automation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate example config
  python -m taktik.core.automation --generate-example
  
  # Run with config file
  python -m taktik.core.automation --config my_config.json
  
  # Validate config without running
  python -m taktik.core.automation --config my_config.json --dry-run
  
  # Verbose logging
  python -m taktik.core.automation --config my_config.json --verbose
        """
    )
    
    parser.add_argument(
        '--config',
        type=str,
        help='Path to configuration JSON file'
    )
    
    parser.add_argument(
        '--generate-example',
        action='store_true',
        help='Generate an example configuration file'
    )
    
    parser.add_argument(
        '--platform',
        type=str,
        choices=['instagram', 'tiktok'],
        default='instagram',
        help='Platform for example config (default: instagram)'
    )
    
    parser.add_argument(
        '--output',
        type=str,
        default='taktik_config_example.json',
        help='Output path for example config (default: taktik_config_example.json)'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Validate configuration without executing'
    )
    
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(args.verbose)
    
    # Generate example
    if args.generate_example:
        generate_example_config(args.output, args.platform)
        return
    
    # Run session
    if args.config:
        run_session(args.config, args.dry_run)
        return
    
    # No action specified
    parser.print_help()
    sys.exit(1)


if __name__ == '__main__':
    main()
