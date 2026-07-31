import { Carousel } from '@/components/carousel/Carousel';
import { CarouselItem } from '@/components/carousel/CarouselItem';
import { expect, test } from 'vitest';
import { render } from 'vitest-browser-react';
import { userEvent } from 'vitest/browser';

const ITEM_WIDTH = 150;
const VIEWPORT_WIDTH = 400;
/** Item pitch: 150px item + the default gap of 2 spacing units. */
const STEP = ITEM_WIDTH + 16;

/** Fixed-width host, so overflow is decided by the test rather than the window. */
const Strip = ({ count }: { count: number }) => (
  <div style={{ width: VIEWPORT_WIDTH }}>
    <Carousel aria-label="Test carousel">
      {Array.from({ length: count }, (_, index) => (
        <CarouselItem key={index}>
          <div style={{ width: ITEM_WIDTH, height: 80 }}>Item {index + 1}</div>
        </CarouselItem>
      ))}
    </Carousel>
  </div>
);

const viewport = () =>
  document.querySelector<HTMLElement>('[role="group"][aria-label="Test carousel"]')!;

test('renders every item it is given', async () => {
  const screen = await render(<Strip count={6} />);

  await expect.element(screen.getByText('Item 1')).toBeInTheDocument();
  await expect.element(screen.getByText('Item 6')).toBeInTheDocument();
});

test('shows no controls while the content fits', async () => {
  const screen = await render(<Strip count={2} />);

  await expect.element(screen.getByText('Item 2')).toBeInTheDocument();
  await expect
    .element(screen.getByRole('button', { name: 'Scroll forward' }))
    .not.toBeInTheDocument();
  await expect.element(screen.getByRole('button', { name: 'Scroll back' })).not.toBeInTheDocument();
});

test('offers only forward paging once the content overflows', async () => {
  const screen = await render(<Strip count={10} />);

  await expect.element(screen.getByRole('button', { name: 'Scroll forward' })).toBeInTheDocument();
  await expect.element(screen.getByRole('button', { name: 'Scroll back' })).not.toBeInTheDocument();
});

test('paging forward lands on an item boundary and reveals the back control', async () => {
  const screen = await render(<Strip count={10} />);

  await userEvent.click(screen.getByRole('button', { name: 'Scroll forward' }));

  // The furthest item start within one page of travel: 400px fits 0 and 166,
  // so a page ends start-aligned on the third item rather than mid-item.
  await expect.poll(() => Math.round(viewport().scrollLeft)).toBe(STEP * 2);
  await expect.element(screen.getByRole('button', { name: 'Scroll back' })).toBeInTheDocument();
});

test('paging back returns to the start and retires the back control', async () => {
  const screen = await render(<Strip count={10} />);

  await userEvent.click(screen.getByRole('button', { name: 'Scroll forward' }));
  await expect.poll(() => Math.round(viewport().scrollLeft)).toBe(STEP * 2);

  await userEvent.click(screen.getByRole('button', { name: 'Scroll back' }));

  await expect.poll(() => Math.round(viewport().scrollLeft)).toBe(0);
  await expect.element(screen.getByRole('button', { name: 'Scroll back' })).not.toBeInTheDocument();
});

test('items land on the content column when the carousel bleeds past its container', async () => {
  const screen = await render(
    <div style={{ width: VIEWPORT_WIDTH, paddingLeft: 24, paddingRight: 24 }}>
      <Carousel aria-label="Test carousel" bleed={3}>
        {Array.from({ length: 10 }, (_, index) => (
          <CarouselItem key={index}>
            <div style={{ width: ITEM_WIDTH, height: 80 }}>Item {index + 1}</div>
          </CarouselItem>
        ))}
      </Carousel>
    </div>
  );

  const restingLeft = document.querySelector('[data-carousel-item]')!.getBoundingClientRect().left;

  await userEvent.click(screen.getByRole('button', { name: 'Scroll forward' }));
  await expect.poll(() => Math.round(viewport().scrollLeft)).toBeGreaterThan(0);

  // Whichever item a page lands on must sit exactly where item 1 rested. If the
  // paging maths ignored the viewport's padding it would be a gutter off.
  await expect
    .poll(() =>
      Array.from(document.querySelectorAll('[data-carousel-item]')).some(
        (item) => Math.abs(item.getBoundingClientRect().left - restingLeft) < 1
      )
    )
    .toBe(true);
});

test('the last item keeps the same margin at the end as the first has at rest', async () => {
  const screen = await render(
    <div style={{ width: VIEWPORT_WIDTH, paddingLeft: 24, paddingRight: 24 }}>
      <Carousel aria-label="Test carousel" bleed={3}>
        {Array.from({ length: 10 }, (_, index) => (
          <CarouselItem key={index}>
            <div style={{ width: ITEM_WIDTH, height: 80 }}>Item {index + 1}</div>
          </CarouselItem>
        ))}
      </Carousel>
    </div>
  );
  await expect.element(screen.getByRole('button', { name: 'Scroll forward' })).toBeInTheDocument();

  const items = Array.from(document.querySelectorAll('[data-carousel-item]'));
  const leadingMargin =
    items[0].getBoundingClientRect().left - viewport().getBoundingClientRect().left;

  viewport().scrollLeft = viewport().scrollWidth;
  await expect.poll(() => Math.round(viewport().scrollLeft)).toBeGreaterThan(0);

  // A scroll container drops its own trailing padding from the scrollable
  // overflow, so this is 0 unless the bleed lives on the track instead.
  const trailingMargin =
    viewport().getBoundingClientRect().right -
    items[items.length - 1].getBoundingClientRect().right;
  expect(Math.round(trailingMargin)).toBe(Math.round(leadingMargin));
});

test('a drag that stops mid-item settles onto the nearest boundary', async () => {
  const screen = await render(<Strip count={10} />);
  await expect.element(screen.getByRole('button', { name: 'Scroll forward' })).toBeInTheDocument();

  viewport().scrollLeft = STEP + 34;
  viewport().dispatchEvent(new Event('scrollend'));

  await expect.poll(() => Math.round(viewport().scrollLeft)).toBe(STEP);
});
