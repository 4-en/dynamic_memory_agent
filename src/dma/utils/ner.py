# static class to share NER model

import spacy

class NER:
    _nlp = spacy.load("en_core_web_sm")

    @staticmethod
    def get_nlp() -> spacy.language.Language:
        """
        Get the NLP model.

        Returns
        -------
        spacy.language.Language
            The NLP model.
        """
        return NER._nlp

    @staticmethod
    def get_entities(text: str) -> list[str]:
        """
        Get named entities from a text.
        
        Parameters
        ----------
        text : str
            The text
        
        Returns
        -------
        list
            A list of entities.
        """
        doc = NER._nlp(text)
        allowed_entities = {"PERSON", "ORG", "GPE", "NORP", "FAC", "LOC", "PRODUCT", "EVENT", "WORK_OF_ART", "LAW", "LANGUAGE"}
        return [ent.text for ent in doc.ents if ent.label_ in allowed_entities]