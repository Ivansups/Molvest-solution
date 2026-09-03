import axios from "axios";

export const adminApiClient = axios.create({
  baseURL: "/api/admin",
  timeout: 10000,
});
