"""Office format metadata used by execution and evidence tools."""

MEDIA_TYPES = {
    "excel": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "word": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "powerpoint": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}
EXPECTED_SUFFIXES = {"excel": ".xlsx", "word": ".docx", "powerpoint": ".pptx"}
OOXML_MEMBERS = {
    "excel": ("[Content_Types].xml", "xl/workbook.xml"),
    "word": ("[Content_Types].xml", "word/document.xml"),
    "powerpoint": ("[Content_Types].xml", "ppt/presentation.xml"),
}
