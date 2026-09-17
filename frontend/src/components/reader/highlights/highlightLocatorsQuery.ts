/** How one book's highlight locators are fetched, by whoever needs them. */
export const LOCATORS_QUERY = {
  // Only a replaced EPUB moves a locator, so a focus refetch would place the whole book
  // again for nothing; and a failure leaves the book unmarked, which is still the book.
  retry: false,
  refetchOnWindowFocus: false,
  staleTime: Infinity,
} as const;
