"""Info Corpus: what OFA knows about the user, in two parts.

    open     "Use without consent": Markdown documents (resume, profile) OFA may read and send to the reasoning
             model to answer questions such as form fields. Stored under data_dir()/corpus/open, never in git.
    private  passwords and secrets: the encrypted vault (ofa/vault). OFA never sees values and asks aloud,
             in detail, before every use (ofa/policy/tiers.py: every vault fill is Tier 2).
"""
from .open import Fact, OpenCorpus

__all__ = ["Fact", "OpenCorpus"]
