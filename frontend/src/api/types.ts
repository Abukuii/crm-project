/** Backend OpenAPI sxemasidan avtomatik generatsiya qilingan tiplarga qisqa nomlar. */
import type { components } from "./schema";

type S = components["schemas"];

export type Me = S["Me"];
export type AuthResponse = S["AuthResponse"];
export type Product = S["Product"];
export type PaginatedProducts = S["PaginatedProductList"];
export type Category = S["Category"];
export type Unit = S["Unit"];
export type PriceType = S["PriceType"];
export type StockBalance = S["StockBalance"];
export type CurrentRate = S["CurrentRate"];
export type Warehouse = S["Warehouse"];
export type Tenant = S["Tenant"];

export type Dashboard = S["Dashboard"];
export type PosProduct = S["PosProduct"];
export type Sale = S["Sale"];
export type SalesSummary = S["SalesSummary"];
export type Customer = S["Customer"];
export type Receivable = S["Receivable"];
export type CustomerPayment = S["CustomerPayment"];

export type Supplier = S["Supplier"];
export type Purchase = S["Purchase"];
export type Statement = S["Statement"];

export type Expense = S["Expense"];
export type ExpenseCategory = S["ExpenseCategory"];
export type Reminder = S["Reminder"];
export type User = S["User"];
export type Role = S["Role"];
export type ImportResult = S["ImportResult"];
export type Shift = S["Shift"];
export type ShiftReport = S["ShiftReport"];
export type CashMove = S["CashMove"];

export interface Page<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

/** Backend xato formati: {"error": {"code", "message", "details"}} */
export interface ApiErrorBody {
  error: { code: string; message: string; details: unknown };
}

export const PAYMENT_LABELS: Record<string, string> = {
  cash: "Naqd",
  card: "Plastik karta",
  transfer: "O'tkazma",
  credit: "Nasiya",
};
