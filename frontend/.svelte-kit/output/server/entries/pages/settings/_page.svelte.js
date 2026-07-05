import { e as escape_html, c as slot, b as attr, d as ensure_array_like } from "../../../chunks/index.js";
import { P as Panel, B as Button } from "../../../chunks/Button.js";
class ApiError extends Error {
  constructor(status, detail) {
    super(`API Error ${status}: ${detail}`);
    this.status = status;
    this.detail = detail;
    this.name = "ApiError";
  }
}
async function parseErrorDetail(response) {
  try {
    const data = await response.json();
    return data.detail || response.statusText || "Unknown error";
  } catch {
    return response.statusText || "Unknown error";
  }
}
async function apiCall(endpoint, options = {}) {
  const response = await fetch(endpoint, {
    ...options,
    credentials: "include",
    headers: {
      ...options.headers
    }
  });
  if (!response.ok) {
    const detail = await parseErrorDetail(response);
    throw new ApiError(response.status, detail);
  }
  if (response.status === 204) {
    return void 0;
  }
  return response.json();
}
async function apiJson(endpoint, method = "GET", body) {
  const options = {
    method,
    headers: {
      "Content-Type": "application/json"
    }
  };
  if (body) {
    options.body = JSON.stringify(body);
  }
  return apiCall(endpoint, options);
}
function Modal($$renderer, $$props) {
  $$renderer.component(($$renderer2) => {
    let { title, open, onClose } = $$props;
    if (open) {
      $$renderer2.push("<!--[0-->");
      $$renderer2.push(`<div class="fixed inset-0 bg-black/50 flex items-center justify-center z-50"><div class="bg-white dark:bg-gray-900 rounded-xl shadow-lg border border-gray-200 dark:border-gray-800 max-w-md w-full mx-4"><div class="flex items-center justify-between p-6 border-b border-gray-200 dark:border-gray-800"><h2 class="text-lg font-semibold text-gray-900 dark:text-white">${escape_html(title)}</h2> <button class="text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 transition">✕</button></div> <div class="p-6"><!--[-->`);
      slot($$renderer2, $$props, "default", {});
      $$renderer2.push(`<!--]--></div></div></div>`);
    } else {
      $$renderer2.push("<!--[-1-->");
    }
    $$renderer2.push(`<!--]-->`);
  });
}
function _page($$renderer, $$props) {
  $$renderer.component(($$renderer2) => {
    let currentPassword = "";
    let newPassword = "";
    let confirmPassword = "";
    let passwordLoading = false;
    let passwordMessage = "";
    let passwordError = "";
    let households = [];
    let showCreateUserModal = false;
    let newUsername = "";
    let newPassword2 = "";
    let newRole = "admin";
    let newUserHouseholdId = null;
    let createUserLoading = false;
    let createUserError = "";
    let showCreateHouseholdModal = false;
    let newHouseholdName = "";
    let createHouseholdLoading = false;
    let createHouseholdError = "";
    async function handleChangePassword() {
      passwordError = "";
      passwordMessage = "";
      {
        passwordError = "All fields required";
        return;
      }
    }
    async function loadAdminData() {
      return;
    }
    async function handleCreateUser() {
      createUserError = "";
      if (!newUsername.trim() || !newPassword2.trim()) {
        createUserError = "Username and password required";
        return;
      }
      if (newPassword2.length < 8) {
        createUserError = "Password must be at least 8 characters";
        return;
      }
      try {
        createUserLoading = true;
        const payload = {
          username: newUsername.trim(),
          password: newPassword2,
          role: newRole
        };
        if (newUserHouseholdId) {
          payload.household_id = newUserHouseholdId;
        }
        await apiJson("/api/admin/users", "POST", payload);
        newUsername = "";
        newPassword2 = "";
        newRole = "admin";
        newUserHouseholdId = null;
        showCreateUserModal = false;
        await loadAdminData();
      } catch (err) {
        if (err instanceof ApiError && err.status === 409) {
          createUserError = "User already exists";
        } else {
          createUserError = err instanceof Error ? err.message : "Failed to create user";
        }
      } finally {
        createUserLoading = false;
      }
    }
    async function handleCreateHousehold() {
      createHouseholdError = "";
      if (!newHouseholdName.trim()) {
        createHouseholdError = "Household name required";
        return;
      }
      try {
        createHouseholdLoading = true;
        await apiJson("/api/admin/households", "POST", { name: newHouseholdName.trim() });
        newHouseholdName = "";
        showCreateHouseholdModal = false;
        await loadAdminData();
      } catch (err) {
        if (err instanceof ApiError && err.status === 409) {
          createHouseholdError = "Household already exists";
        } else {
          createHouseholdError = err instanceof Error ? err.message : "Failed to create household";
        }
      } finally {
        createHouseholdLoading = false;
      }
    }
    $$renderer2.push(`<div class="max-w-6xl mx-auto px-4 py-8"><div class="mb-8 flex items-center gap-3"><h1 class="text-2xl uppercase font-bold tracking-widest text-bright glow-cyan">// SETTINGS</h1></div> `);
    Panel($$renderer2, {
      title: "ACCOUNT",
      children: ($$renderer3) => {
        $$renderer3.push(`<div class="max-w-md space-y-6"><div><h3 class="label mb-4">Change Password</h3> `);
        if (passwordError) {
          $$renderer3.push("<!--[0-->");
          $$renderer3.push(`<div class="mb-4 p-3 border border-danger text-danger text-sm">${escape_html(passwordError)}</div>`);
        } else {
          $$renderer3.push("<!--[-1-->");
        }
        $$renderer3.push(`<!--]--> `);
        if (passwordMessage) {
          $$renderer3.push("<!--[0-->");
          $$renderer3.push(`<div class="mb-4 p-3 border border-success text-success text-sm">${escape_html(passwordMessage)}</div>`);
        } else {
          $$renderer3.push("<!--[-1-->");
        }
        $$renderer3.push(`<!--]--> <div class="space-y-4"><div><div class="label mb-2">Current Password</div> <input type="password"${attr("value", currentPassword)}${attr("disabled", passwordLoading, true)} class="input w-full text-sm disabled:opacity-50"/></div> <div><div class="label mb-2">New Password</div> <input type="password"${attr("value", newPassword)}${attr("disabled", passwordLoading, true)} class="input w-full text-sm disabled:opacity-50"/></div> <div><div class="label mb-2">Confirm New Password</div> <input type="password"${attr("value", confirmPassword)}${attr("disabled", passwordLoading, true)} class="input w-full text-sm disabled:opacity-50"/></div> `);
        Button($$renderer3, {
          onclick: handleChangePassword,
          disabled: passwordLoading,
          variant: "primary",
          children: ($$renderer4) => {
            $$renderer4.push(`<!---->${escape_html("[ UPDATE PASSWORD ]")}`);
          }
        });
        $$renderer3.push(`<!----></div></div></div>`);
      }
    });
    $$renderer2.push(`<!----> `);
    {
      $$renderer2.push("<!--[-1-->");
    }
    $$renderer2.push(`<!--]--></div> `);
    Modal($$renderer2, {
      title: "CREATE NEW USER",
      open: showCreateUserModal,
      onClose: () => showCreateUserModal = false,
      children: ($$renderer3) => {
        if (createUserError) {
          $$renderer3.push("<!--[0-->");
          $$renderer3.push(`<div class="mb-4 p-3 border border-danger text-danger text-sm">${escape_html(createUserError)}</div>`);
        } else {
          $$renderer3.push("<!--[-1-->");
        }
        $$renderer3.push(`<!--]--> <div class="space-y-4"><div><div class="label mb-2">Username</div> <input type="text"${attr("value", newUsername)}${attr("disabled", createUserLoading, true)} placeholder="newuser" class="input w-full text-sm disabled:opacity-50"/></div> <div><div class="label mb-2">Password</div> <input type="password"${attr("value", newPassword2)}${attr("disabled", createUserLoading, true)} placeholder="min 8 characters" class="input w-full text-sm disabled:opacity-50"/></div> <div><div class="label mb-2">Role</div> `);
        $$renderer3.select(
          {
            value: newRole,
            disabled: createUserLoading,
            class: "input w-full text-sm disabled:opacity-50"
          },
          ($$renderer4) => {
            $$renderer4.option({ value: "admin" }, ($$renderer5) => {
              $$renderer5.push(`Admin`);
            });
            $$renderer4.option({ value: "member" }, ($$renderer5) => {
              $$renderer5.push(`Member`);
            });
            $$renderer4.option({ value: "viewer" }, ($$renderer5) => {
              $$renderer5.push(`Viewer`);
            });
          }
        );
        $$renderer3.push(`</div> <div><div class="label mb-2">Household (optional)</div> `);
        $$renderer3.select(
          {
            value: newUserHouseholdId,
            disabled: createUserLoading,
            class: "input w-full text-sm disabled:opacity-50"
          },
          ($$renderer4) => {
            $$renderer4.option({ value: null }, ($$renderer5) => {
              $$renderer5.push(`None`);
            });
            $$renderer4.push(`<!--[-->`);
            const each_array_3 = ensure_array_like(households);
            for (let $$index_3 = 0, $$length = each_array_3.length; $$index_3 < $$length; $$index_3++) {
              let h = each_array_3[$$index_3];
              $$renderer4.option({ value: h.id }, ($$renderer5) => {
                $$renderer5.push(`${escape_html(h.name)}`);
              });
            }
            $$renderer4.push(`<!--]-->`);
          }
        );
        $$renderer3.push(`</div> <div class="flex gap-3 pt-4">`);
        Button($$renderer3, {
          onclick: handleCreateUser,
          disabled: createUserLoading,
          variant: "primary",
          children: ($$renderer4) => {
            $$renderer4.push(`<!---->${escape_html(createUserLoading ? "CREATING..." : "[ CREATE ]")}`);
          }
        });
        $$renderer3.push(`<!----> `);
        Button($$renderer3, {
          onclick: () => showCreateUserModal = false,
          disabled: createUserLoading,
          variant: "ghost",
          children: ($$renderer4) => {
            $$renderer4.push(`<!---->Cancel`);
          }
        });
        $$renderer3.push(`<!----></div></div>`);
      },
      $$slots: { default: true }
    });
    $$renderer2.push(`<!----> `);
    Modal($$renderer2, {
      title: "CREATE HOUSEHOLD",
      open: showCreateHouseholdModal,
      onClose: () => showCreateHouseholdModal = false,
      children: ($$renderer3) => {
        if (createHouseholdError) {
          $$renderer3.push("<!--[0-->");
          $$renderer3.push(`<div class="mb-4 p-3 border border-danger text-danger text-sm">${escape_html(createHouseholdError)}</div>`);
        } else {
          $$renderer3.push("<!--[-1-->");
        }
        $$renderer3.push(`<!--]--> <div class="space-y-4"><div><div class="label mb-2">Household Name</div> <input type="text"${attr("value", newHouseholdName)}${attr("disabled", createHouseholdLoading, true)} placeholder="e.g., Smith Family" class="input w-full text-sm disabled:opacity-50"/></div> <div class="flex gap-3 pt-4">`);
        Button($$renderer3, {
          onclick: handleCreateHousehold,
          disabled: createHouseholdLoading,
          variant: "primary",
          children: ($$renderer4) => {
            $$renderer4.push(`<!---->${escape_html(createHouseholdLoading ? "CREATING..." : "[ CREATE ]")}`);
          }
        });
        $$renderer3.push(`<!----> `);
        Button($$renderer3, {
          onclick: () => showCreateHouseholdModal = false,
          disabled: createHouseholdLoading,
          variant: "ghost",
          children: ($$renderer4) => {
            $$renderer4.push(`<!---->Cancel`);
          }
        });
        $$renderer3.push(`<!----></div></div>`);
      },
      $$slots: { default: true }
    });
    $$renderer2.push(`<!---->`);
  });
}
export {
  _page as default
};
