"""ai-analytics-ontology: the marts ontology as a closed-world graph for deciding answerability."""
from . import parameters
from .graph import MartsOntology

__all__ = ["MartsOntology", "parameters"]
