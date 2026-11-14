SAHAYAK AI — MULTILINGUAL FAQ / KNOWLEDGE PACK

Files:
- sahayak_ai_training_dataset.json: 100 structured Q&A examples, suitable for a retrieval/knowledge-base import.
- sahayak_ai_100_qa.csv: spreadsheet-friendly table with English questions and answers in English, Hindi, Kannada and Tamil.

This is a curated FAQ/response dataset, not model fine-tuning. For a production RAG system, index current official EPFO and ESIC guidance plus company-approved HR/payroll policies. Re-verify policy text and effective dates before use.

Agent behaviour instructions:
1. Accept a worker question typed in English; identify intent even if phrased informally.
2. Retrieve an approved source passage and the closest FAQ before answering.
3. Respond in the selected language: Hindi (hi), Kannada (kn), or Tamil (ta). Offer a separate English translation toggle.
4. Use plain spoken language and short steps. Explain jargon.
5. Never invent an employee balance, deduction, contribution rate, claim timeline, eligibility, tax result or approval. If records/sources are missing, say so and escalate.
6. Access personal payroll/insurance records only after authentication, explicit consent and permission checks. Retrieve only the minimum required fields.
7. Create an HR ticket only after identity, consent and destination are confirmed. Log the action. The examples here do not create real tickets.
8. Never request or accept OTPs, passwords, PINs, full Aadhaar/PAN or full bank details in chat.
9. Escalate disputes, claim rejections, accident/death cases, uncertain rules and all individual financial/eligibility decisions to a human.
10. Attach source name, retrieval date and confidence to every production answer.

Official reference sources (confirm current instructions before deployment):
EPFO Member Portal: https://unifiedportal-mem.epfindia.gov.in/memberinterface/
EPFO UAN/KYC FAQ: https://www.epfindia.gov.in/site_docs/PDFs/Circulars/Y2020-2021/FAQUANKYC.pdf
EPFO Transfer FAQ: https://www.epfindia.gov.in/site_docs/PDFs/Circulars/Y2020-2021/faq_transfer_claim.pdf
EPFiGMS: https://epfigms.gov.in/
UMANG: https://web.umang.gov.in/
ESIC: https://www.esic.gov.in/
ESIC scheme pamphlet: https://esic.gov.in/PAMPHLETS/ENGLISH.pdf
