# RMIT University Vietnam
# Course: COSC2767|COSC2805 Systems Deployment and Operations
# Semester: 2026B
# Assessment: Assignment 2
# Author: Vo Hoang Khanh
# ID: s3926310
# Created  date: 02/09/2026
# Last modified: 02/09/2026
# Acknowledgement: Drafted with Claude (Anthropic) in a guided session; the
#   author reviewed and verified the package layout. Reference:
#   pytest test discovery, https://docs.pytest.org/en/stable/explanation/goodpractices.html

# Present so pytest imports test modules as a package.
# Without it, tests/unit/test_payments.py and tests/integration/test_payments.py
# collide on the module name "test_payments" and pytest aborts collection.
