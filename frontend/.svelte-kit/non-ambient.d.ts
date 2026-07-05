
// this file is generated — do not edit it


declare module "svelte/elements" {
	export interface HTMLAttributes<T> {
		'data-sveltekit-keepfocus'?: true | '' | 'off' | undefined | null;
		'data-sveltekit-noscroll'?: true | '' | 'off' | undefined | null;
		'data-sveltekit-preload-code'?:
			| true
			| ''
			| 'eager'
			| 'viewport'
			| 'hover'
			| 'tap'
			| 'off'
			| undefined
			| null;
		'data-sveltekit-preload-data'?: true | '' | 'hover' | 'tap' | 'off' | undefined | null;
		'data-sveltekit-reload'?: true | '' | 'off' | undefined | null;
		'data-sveltekit-replacestate'?: true | '' | 'off' | undefined | null;
	}
}

export {};


declare module "$app/types" {
	type MatcherParam<M> = M extends (param : string) => param is (infer U extends string) ? U : string;

	export interface AppTypes {
		RouteId(): "/" | "/document" | "/document/[id]" | "/inbox" | "/login" | "/search" | "/settings" | "/setup";
		RouteParams(): {
			"/document/[id]": { id: string }
		};
		LayoutParams(): {
			"/": { id?: string | undefined };
			"/document": { id?: string | undefined };
			"/document/[id]": { id: string };
			"/inbox": Record<string, never>;
			"/login": Record<string, never>;
			"/search": Record<string, never>;
			"/settings": Record<string, never>;
			"/setup": Record<string, never>
		};
		Pathname(): "/" | `/document/${string}` & {} | "/inbox" | "/login" | "/search" | "/settings" | "/setup";
		ResolvedPathname(): `${"" | `/${string}`}${ReturnType<AppTypes['Pathname']>}`;
		Asset(): string & {};
	}
}