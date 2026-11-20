/** Backend OpenAPI sxemasidan avtomatik generatsiya qilingan tiplarga qisqa nomlar. */
import type { components } from "./schema";

type S = components["schemas"];

export type Me = S["Me"];
export type AuthResponse = S["AuthResponse"];
export type Product = S["Product"];
export type PaginatedProducts = S["PaginatedProductList"];
export type Category = S["Category"];
export type Unit = S["Unit"];
export type StockBalance = S["StockBalance"];
export type CurrentRate = S["CurrentRate"];

/** Backend xato formati: {"error": {"code", "message", "details"}} */
export interface ApiErrorBody {
  error: { code: string; message: string; details: unknown };
}
