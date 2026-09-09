# Testing

Run before committing:

```bash
python3 -m unittest discover -s workbench -p 'test_*.py'
python3 workbench/server.py self-test
python3 -m py_compile workbench/server.py toolkit/*.py
zsh -n workbench/打开公众号排版器.command
```

The workbench also contains browser assertions for theme count, component parsing, SVG animation nodes, WeChat image URL handling, and exported HTML safety.

For visible QA, start `python3 workbench/server.py`, open `http://127.0.0.1:8766/`, and verify article input, theme switching, image slots, WeChat upload status, and HTML copy.
