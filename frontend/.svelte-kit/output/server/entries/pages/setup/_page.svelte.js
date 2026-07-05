import { b as attr, e as escape_html } from "../../../chunks/index.js";
import "@sveltejs/kit/internal";
import "../../../chunks/exports.js";
import "../../../chunks/utils2.js";
import "@sveltejs/kit/internal/server";
import "../../../chunks/root.js";
import "../../../chunks/state.svelte.js";
import { P as Panel, B as Button } from "../../../chunks/Button.js";
function _page($$renderer, $$props) {
  $$renderer.component(($$renderer2) => {
    let passphrase = "";
    let passphraseConfirm = "";
    let adminUsername = "";
    let adminPassword = "";
    let loading = false;
    $$renderer2.push(`<div class="min-h-screen flex items-center justify-center px-4 py-8 bg-ink font-mono"><div class="w-full max-w-md">`);
    Panel($$renderer2, {
      title: "SYSTEM INITIALIZATION",
      children: ($$renderer3) => {
        $$renderer3.push(`<div class="text-xs text-muted mb-6 space-y-1 leading-relaxed"><div></div> <div class="text-cyan">> Initializing secure vault infrastructure...</div> <div class="text-cyan">> Configure master credentials</div></div> `);
        {
          $$renderer3.push("<!--[-1-->");
        }
        $$renderer3.push(`<!--]--> <form class="space-y-4"><div><label class="label mb-2">MASTER PASSPHRASE</label> <input type="password"${attr("value", passphrase)}${attr("disabled", loading, true)} placeholder="min 12 chars" class="input"/></div> <div><label class="label mb-2">CONFIRM PASSPHRASE</label> <input type="password"${attr("value", passphraseConfirm)}${attr("disabled", loading, true)} placeholder="confirm" class="input"/></div> <div><label class="label mb-2">OPERATOR ID</label> <input type="text"${attr("value", adminUsername)}${attr("disabled", loading, true)} placeholder="admin username" class="input"/></div> <div><label class="label mb-2">OPERATOR PASSWORD</label> <input type="password"${attr("value", adminPassword)}${attr("disabled", loading, true)} placeholder="min 8 chars" class="input"/></div> <div class="pt-4">`);
        Button($$renderer3, {
          variant: "primary",
          type: "submit",
          disabled: loading,
          loading,
          children: ($$renderer4) => {
            $$renderer4.push(`<!---->${escape_html("INITIALIZE VAULT")}`);
          }
        });
        $$renderer3.push(`<!----></div></form> <div class="text-xs text-muted mt-6 pt-4 border-t border-line"></div>`);
      }
    });
    $$renderer2.push(`<!----></div></div>`);
  });
}
export {
  _page as default
};
