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

test('a drag that stops mid-item settles onto the nearest boundary', async () => {
  const screen = await render(<Strip count={10} />);
  await expect.element(screen.getByRole('button', { name: 'Scroll forward' })).toBeInTheDocument();

  viewport().scrollLeft = STEP + 34;
  viewport().dispatchEvent(new Event('scrollend'));

  await expect.poll(() => Math.round(viewport().scrollLeft)).toBe(STEP);
});
