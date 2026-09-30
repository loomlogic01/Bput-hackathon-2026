import json
from pyexpat.errors import messages
from importlib import import_module

try:
    DocumentConverter = import_module("docling.document_converter").DocumentConverter
except ModuleNotFoundError as e:
    raise ImportError(
        "Docling is required. Install it with: pip install docling"
    ) from e
from pydantic import BaseModel, Field
import ollama

class UtilityBillSchema(BaseModel):
    matric_type: str = Field(..., description="ELECTRICITY, WATER, DIESEL, OR WASTE")
    raw_value: float = Field(..., description="Numerical consumption amount")
    unit: str = Field(..., description="kWh, Liters, MT")
    billing_period: str = Field(..., description="Month and Year of billing e.g; September 2026")
    
def parse_pdf(pdf_path: str):
    # Convert to markdown via Docling
    converter = DocumentConverter()
    doc_result = converter.convert(pdf_path)
    markdown_text = doc_result.document.export_to_markdown()
    # Extraction via Ollama
    response = ollama.chat(
        model="llama3.1:8b",
        messages=[{
            "role": "user",
            "content": (f"Extracted ESG matrics from this bill text:\n\n{markdown_text}"),
        }],
        format=UtilityBillSchema.model_json_schema(),
    )
    
    data = json.loads(response["message"]["content"])
    validated_data = UtilityBillSchema(**data)
    print("Extraced Data Successfully:", validated_data)
    
    if __name__ == "__main__":
        parse_pdf("sample_electricity_bill.pdf")
    