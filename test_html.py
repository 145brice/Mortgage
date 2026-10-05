from dashboard import HTML_TEMPLATE
import re

# Extract just the thead section
match = re.search(r'<thead>.*?</thead>', HTML_TEMPLATE, re.DOTALL)
if match:
    print(match.group(0))
