#!/usr/bin/env python3
"""
Generate fresh digests with the new simplified 2-topic structure
"""

import os
import sys
import logging
from pathlib import Path
from datetime import date

# Add src to Python path
sys.path.append(str(Path(__file__).parent / 'src'))

from generation.script_generator import ScriptGenerator
from database.models import get_database_manager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def generate_fresh_digests():
    """Generate fresh digests with new topic structure"""
    
    logger.info("Generating fresh digests with new 2-topic structure...")
    
    # Initialize
    script_gen = ScriptGenerator()
    
    # Generate for today (2025-09-09)
    today = date(2025, 9, 9)
    
    try:
        results = script_gen.generate_all_digests(today)
        
        print(f'\n✅ DIGEST GENERATION RESULTS:')
        generated_count = 0
        skipped_count = 0
        
        for result in results:
            if result['generated']:
                generated_count += 1
                print(f'  ✅ {result["topic"]}: {result["word_count"]} words, {result["episode_count"]} episodes')
                print(f'     Script: {result["script_path"]}')
            else:
                skipped_count += 1
                print(f'  ⏭️  {result["topic"]}: {result["reason"]}')
        
        print(f'\n📊 SUMMARY:')
        print(f'  Generated: {generated_count} digests')
        print(f'  Skipped: {skipped_count} digests')
        
        return generated_count > 0
        
    except Exception as e:
        logger.error(f"Failed to generate digests: {e}")
        return False

if __name__ == "__main__":
    success = generate_fresh_digests()
    sys.exit(0 if success else 1)