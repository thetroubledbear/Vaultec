import "clsx";
import "@sveltejs/kit/internal";
import "../../chunks/exports.js";
import "../../chunks/utils2.js";
import "@sveltejs/kit/internal/server";
import "../../chunks/root.js";
import "../../chunks/state.svelte.js";
/* empty css                                               */
function _page($$renderer, $$props) {
  $$renderer.component(($$renderer2) => {
    $$renderer2.push(`<div class="max-w-7xl mx-auto px-4 py-8">`);
    {
      $$renderer2.push("<!--[0-->");
      $$renderer2.push(`<div class="mb-8 p-6 bg-amber-50 dark:bg-amber-900/20 border-2 border-amber-200 dark:border-amber-800 rounded-lg"><h2 class="text-lg font-semibold text-amber-900 dark:text-amber-200 mb-2">🔒 Vault is Locked</h2> <p class="text-amber-800 dark:text-amber-300 mb-4">Your vault has been locked. Use the Unlock button in the top bar to unlock it with your master passphrase.</p></div>`);
    }
    $$renderer2.push(`<!--]--></div>`);
  });
}
export {
  _page as default
};
