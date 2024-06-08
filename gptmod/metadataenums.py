print("importing metadataenums")
from enum import Enum


class MetadataDocType(Enum):
    error = -5
    htmltext = 0
    readertext = 1
    pdftext = 2

    def __int__(self):
        return self.value
