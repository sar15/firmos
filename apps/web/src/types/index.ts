import { z } from "zod";

export const MoneySchema = z.object({
  /** integer paise to avoid float drift on tax amounts */
  paise: z.number().int(),
  currency: z.literal("INR"),
});

export const ClientSchema = z.object({
  id: z.string(),
  legalName: z.string(),
  pan: z.string(),
  gstin: z.string().nullable(),
  entityType: z.enum(["PRIVATE_LIMITED", "LLP", "PROPRIETOR", "PARTNERSHIP"]),
  state: z.string(),
  booksProvider: z.enum(["ZOHO_BOOKS", "TALLY", "QUICKBOOKS", "CSV", "NONE"]).nullable(),
  nextDue: z.string(),
  complianceStatus: z.enum(["ON_TRACK", "DUE_SOON", "OVERDUE", "READY"]),
});
export type Client = z.infer<typeof ClientSchema>;

export const DecisionSchema = z.object({
  id: z.string(),
  clientId: z.string(),
  kind: z.enum(["TDS_DEFAULT", "GST_NOTICE", "GSTR_APPROVAL", "ITR_APPROVAL", "RECONCILIATION"]),
  title: z.string(),
  firmOsRecommendation: z.string(),
  urgency: z.enum(["NEEDS_YOU_NOW", "DUE_TODAY", "THIS_WEEK"]),
  amountAtStake: MoneySchema.nullable(),
  dueDate: z.string(), // ISO
  confidence: z.number().min(0).max(1),
});
export type Decision = z.infer<typeof DecisionSchema>;

export const ConnectorStatus = z.enum(["CONNECTED", "DISCONNECTED", "NEEDS_ATTENTION"]);
export const ConnectorSchema = z.object({
  id: z.string(),
  name: z.string(),
  category: z.enum(["FEATURED", "ACCOUNTING", "GOVERNMENT", "BANKING", "DOCS", "DEVELOPER"]),
  description: z.string(),
  status: ConnectorStatus,
  authMethod: z.enum(["OAUTH", "CREDENTIALS", "API_KEY", "CONSENT"]),
  lastSyncedAt: z.string().nullable(),
});
export type Connector = z.infer<typeof ConnectorSchema>;

export type Category = {
  title: string;
  caption?: string;
  items: Connector[];
};

export const isConnected = (c: Connector): boolean =>
  c.status !== "DISCONNECTED";

export const AuditEntrySchema = z.object({
  id: z.string(),
  timestamp: z.string(),
  actor: z.enum(["firmOS", "HUMAN"]),
  actorName: z.string(),
  action: z.enum(["PORTAL_SUBMITTED", "HUMAN_APPROVED", "STEP_COMPLETED", "DATA_READ", "DOCUMENT_EXTRACTED"]),
  description: z.string(),
  confidence: z.number().min(0).max(1).nullable(),
});
export type AuditEntry = z.infer<typeof AuditEntrySchema>;

// Document Review types
export const ConfidenceLevelSchema = z.enum(["HIGH", "REVIEW", "LOW"]);
export type ConfidenceLevel = z.infer<typeof ConfidenceLevelSchema>;

export const BboxSchema = z.object({
  page: z.number(),
  x: z.number(),
  y: z.number(),
  w: z.number(),
  h: z.number(),
});
export type Bbox = z.infer<typeof BboxSchema>;

export const ExtractedFieldSchema = z.object({
  key: z.string(),
  label: z.string(),
  value: z.string(),
  confidence: z.number().min(0).max(1),
  level: ConfidenceLevelSchema,
  bbox: BboxSchema.optional(),
});
export type ExtractedField = z.infer<typeof ExtractedFieldSchema>;

export const DocStatusSchema = z.enum(["PENDING_REVIEW", "POSTED", "REJECTED", "NEEDS_INFO"]);
export type DocStatus = z.infer<typeof DocStatusSchema>;

export const LineItemSchema = z.object({
  desc: z.string(),
  hsn: z.string().optional(),
  qty: z.number(),
  rate: z.number(),
  amount: z.number(),
});
export type LineItem = z.infer<typeof LineItemSchema>;

export const ExtractedDocumentSchema = z.object({
  id: z.string(),
  clientId: z.string(),
  clientName: z.string(),
  fileUrl: z.string(),
  fileType: z.enum(["pdf", "image", "spreadsheet"]),
  docKind: z.enum(["VENDOR_BILL", "SALES_INVOICE", "RECEIPT", "PAYMENT", "JOURNAL"]),
  status: DocStatusSchema,
  vendorName: z.string(),
  fields: z.array(ExtractedFieldSchema),
  lineItems: z.array(LineItemSchema),
  total: z.number(),
  uploadedAt: z.string(),
});
export type ExtractedDocument = z.infer<typeof ExtractedDocumentSchema>;

// Reconciliation Workspace types
export const ReconModeSchema = z.enum(["BANK_STATEMENT", "GSTR2B_VS_PURCHASE"]);
export type ReconMode = z.infer<typeof ReconModeSchema>;

export const MatchStatusSchema = z.enum(["AUTO_MATCHED", "SUGGESTED", "UNMATCHED"]);
export type MatchStatus = z.infer<typeof MatchStatusSchema>;

export const ReconLineSchema = z.object({
  id: z.string(),
  date: z.string(), // ISO date
  description: z.string(),
  counterparty: z.string(),
  amount: z.number(), // in paise
  ref: z.string().optional(),
  gstin: z.string().optional(),
});
export type ReconLine = z.infer<typeof ReconLineSchema>;

export const ReconMatchSchema = z.object({
  id: z.string(),
  status: MatchStatusSchema,
  score: z.number().min(0).max(1).optional(),
  source: ReconLineSchema.nullable(),
  target: ReconLineSchema.nullable().optional(),
  flag: z.enum(["SUPPLIER_NOT_FILED", "PORTAL_ENTRY_NOT_IN_BOOKS", "AMOUNT_MISMATCH", "DATE_DRIFT"]).optional(),
  reasons: z.array(z.string()).optional(),
}).refine(match => Boolean(match.source || match.target), { message: "A reconciliation match must contain a books or portal record." });
export type ReconMatch = z.infer<typeof ReconMatchSchema>;
