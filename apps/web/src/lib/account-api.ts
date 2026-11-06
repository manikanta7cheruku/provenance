import { request, type MessageResponse } from "./api";

export const EXPORT_PATH = "/api/v1/account/export";
export const DELETE_PHRASE = "delete my account";

/** Ask for the account to be deleted. The password and the typed words are checked on the server. */
export function deleteAccount(
  password: string,
  confirm: string,
): Promise<MessageResponse> {
  return request<MessageResponse>("POST", "/api/v1/account/delete", {
    body: { password, confirm },
  });
}
