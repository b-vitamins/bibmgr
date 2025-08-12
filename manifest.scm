;; Guix manifest for bibmgr - Bibliography Management System
;; Usage: guix shell -m manifest.scm

(specifications->manifest
 '(;; Python runtime
   "python"
   "python-pip"
   
   ;; Core dependencies for search and data
   "python-click"           ; CLI framework
   "python-rich"            ; Terminal formatting
   "python-whoosh"          ; Full-text search engine
   "python-msgspec"         ; Fast serialization
   "python-rapidfuzz"       ; Fuzzy string matching
   "python-structlog"       ; Structured logging
   "python-diskcache"       ; Disk-based caching
   "python-bibtexparser"    ; BibTeX parsing
   "python-pyenchant"       ; Spell checking
   
   ;; Development tools
   "python-pytest"          ; Testing framework
   "python-pytest-cov"      ; Coverage plugin
   "python-pytest-benchmark" ; Benchmark plugin
   "python-pytest-asyncio"  ; Async testing support
   "python-ruff"            ; Linter and formatter
   "node-pyright"           ; Type checker
   "python-ipython"         ; Interactive shell
   
   ;; Build tools
   "poetry"                 ; Dependency management
   "git"                    ; Version control
   "make"                   ; Build automation
   
   ;; Optional but useful
   "python-pyyaml"          ; YAML support
   "python-tomli"           ; TOML parsing
   "python-typing-extensions" ; Backported typing features
   ))