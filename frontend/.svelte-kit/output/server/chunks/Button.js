import { aa as attr_class, ab as stringify, e as escape_html, b as attr, a9 as derived } from "./index.js";
import "clsx";
/* empty css                                    */
function StatusDot($$renderer, $$props) {
  $$renderer.component(($$renderer2) => {
    const { tone = "cyan", pulse = false } = $$props;
    const toneColor = {
      cyan: "bg-cyan",
      amber: "bg-amber",
      danger: "bg-danger",
      success: "bg-success",
      muted: "bg-muted"
    }[tone];
    $$renderer2.push(`<span${attr_class(`status-dot ${stringify(toneColor)} ${pulse ? "status-pulse" : ""}`)}></span>`);
  });
}
function Panel($$renderer, $$props) {
  const { title, subtitle, children, right } = $$props;
  $$renderer.push(`<div class="hud-panel hud-corners">`);
  if (title || right) {
    $$renderer.push("<!--[0-->");
    $$renderer.push(`<div class="flex items-center justify-between mb-3 pb-3 border-b border-line"><div>`);
    if (title) {
      $$renderer.push("<!--[0-->");
      $$renderer.push(`<div class="flex items-center gap-2"><h2 class="text-sm uppercase font-bold tracking-widest text-bright glow-cyan">${escape_html(title)}</h2> `);
      if (!subtitle) {
        $$renderer.push("<!--[0-->");
        StatusDot($$renderer, { pulse: true, tone: "cyan" });
      } else {
        $$renderer.push("<!--[-1-->");
      }
      $$renderer.push(`<!--]--></div>`);
    } else {
      $$renderer.push("<!--[-1-->");
    }
    $$renderer.push(`<!--]--> `);
    if (subtitle) {
      $$renderer.push("<!--[0-->");
      $$renderer.push(`<p class="text-xs text-muted uppercase tracking-wider mt-1">${escape_html(subtitle)}</p>`);
    } else {
      $$renderer.push("<!--[-1-->");
    }
    $$renderer.push(`<!--]--></div> `);
    if (right) {
      $$renderer.push("<!--[0-->");
      $$renderer.push(`<div>`);
      right($$renderer);
      $$renderer.push(`<!----></div>`);
    } else {
      $$renderer.push("<!--[-1-->");
    }
    $$renderer.push(`<!--]--></div>`);
  } else {
    $$renderer.push("<!--[-1-->");
  }
  $$renderer.push(`<!--]--> `);
  if (children) {
    $$renderer.push("<!--[0-->");
    $$renderer.push(`<div>`);
    children($$renderer);
    $$renderer.push(`<!----></div>`);
  } else {
    $$renderer.push("<!--[-1-->");
  }
  $$renderer.push(`<!--]--></div>`);
}
function Button($$renderer, $$props) {
  $$renderer.component(($$renderer2) => {
    const {
      variant = "primary",
      disabled = false,
      loading = false,
      type = "button",
      onclick,
      children
    } = $$props;
    const variantClass = derived(() => ({
      primary: "btn-primary",
      danger: "btn-danger",
      ghost: "btn-ghost",
      success: "btn-success"
    })[variant]);
    $$renderer2.push(`<button${attr("type", type)}${attr("disabled", disabled || loading, true)}${attr_class(`btn ${stringify(variantClass())}`)}>`);
    if (loading) {
      $$renderer2.push("<!--[0-->");
      $$renderer2.push(`<span class="inline-block w-3 h-3 border border-current border-t-transparent rounded-full animate-spin mr-2"></span>`);
    } else {
      $$renderer2.push("<!--[-1-->");
    }
    $$renderer2.push(`<!--]--> `);
    if (children) {
      $$renderer2.push("<!--[0-->");
      children($$renderer2);
      $$renderer2.push(`<!---->`);
    } else {
      $$renderer2.push("<!--[-1-->");
    }
    $$renderer2.push(`<!--]--></button>`);
  });
}
export {
  Button as B,
  Panel as P
};
