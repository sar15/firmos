import { z } from "zod";

export const SalesRegisterRowSchema = z.object({
  id: z.string(),
  invoiceNumber: z.string(),
  customerName: z.string(),
  customerGstin: z.string().default(""),
  invoiceDate: z.string(),
  placeOfSupply: z.string().default(""),
  taxablePaise: z.number().default(0),
  cgstPaise: z.number().default(0),
  sgstPaise: z.number().default(0),
  igstPaise: z.number().default(0),
  cessPaise: z.number().default(0),
  totalPaise: z.number(),
  taxTotalPaise: z.number(),
  status: z.string(),
  provider: z.string().default("EXTERNAL"),
  providerObjectId: z.string().default(""),
  documentId: z.string().default(""),
  financeActionId: z.string().default(""),
  verificationId: z.string().default(""),
  sourceVersion: z.string().default(""),
  eInvoice: z.record(z.string(), z.unknown()).default({}),
  evidence: z.array(z.record(z.string(), z.unknown())).default([]),
  verified: z.boolean().default(false),
});

export type SalesRegisterRow = z.infer<typeof SalesRegisterRowSchema>;

export const PurchaseRegisterRowSchema = z.object({
  id: z.string(),
  billNumber: z.string(),
  vendorName: z.string(),
  vendorGstin: z.string(),
  billDate: z.string(),
  totalPaise: z.number(),
  taxTotalPaise: z.number(),
  source: z.enum(["ZOHO", "ZOHO_BOOKS", "TALLY_PRIME", "LOCAL_OCR", "EXTERNAL"]),
  status: z.string(),
  providerObjectId: z.string().default(""),
  documentId: z.string().default(""),
  financeActionId: z.string().default(""),
  verificationId: z.string().default(""),
  evidence: z.array(z.record(z.string(), z.unknown())).default([]),
  verified: z.boolean().default(false),
});

export type PurchaseRegisterRow = z.infer<typeof PurchaseRegisterRowSchema>;
