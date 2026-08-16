"""
Root Entrypoint for GenAR Pharmacovigilance Periodic Safety Reporting System.
Executes end-to-end report generation, review tracking, assembly, and automated evaluation.
"""

from src.pipeline import main

if __name__ == "__main__":
    main()
