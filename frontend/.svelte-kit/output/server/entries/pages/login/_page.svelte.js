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
    let username = "";
    let password = "";
    let loading = false;
    $$renderer2.push(`<div class="min-h-screen flex items-center justify-center px-4 py-8 bg-ink font-mono"><div class="w-full max-w-md">`);
    Panel($$renderer2, {
      title: "TERMINAL AUTH",
      children: ($$renderer3) => {
        $$renderer3.push(`<div class="text-xs text-muted mb-6 space-y-1 leading-relaxed"><div></div> <div class="text-cyan">> Initiating secure authentication protocol...</div></div> `);
        {
          $$renderer3.push("<!--[-1-->");
        }
        $$renderer3.push(`<!--]--> <form class="space-y-4"><div><label class="label mb-2">USERNAME</label> <input type="text"${attr("value", username)}${attr("disabled", loading, true)} placeholder="operator ID" class="input"/></div> <div><label class="label mb-2">PASSWORD</label> <input type="password"${attr("value", password)}${attr("disabled", loading, true)} placeholder="••••••••••" class="input"/></div> <div class="pt-4">`);
        Button($$renderer3, {
          variant: "primary",
          type: "submit",
          disabled: loading,
          loading,
          children: ($$renderer4) => {
            $$renderer4.push(`<!---->${escape_html("AUTHENTICATE")}`);
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
