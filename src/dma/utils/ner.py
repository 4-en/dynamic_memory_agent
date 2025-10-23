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
    def normalize_entity(entity: str) -> str:
        """
        Normalize an entity string.

        Parameters
        ----------
        entity : str
            The entity string.

        Returns
        -------
        str
            The normalized entity string.
        """
        ent = entity.strip().lower()
        ent = "-".join(ent.split())
        return ent

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
        entities = [ent.text for ent in doc.ents if ent.label_ in allowed_entities]
        
        # normalize entities
        entities = [NER.normalize_entity(ent) for ent in entities]
        return list(set(entities))  # return unique entities