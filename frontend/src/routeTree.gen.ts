import { rootRoute } from "@/routes/__root";
import { indexRoute } from "@/routes/index";
import { replyStrategiesRoute } from "@/routes/reply-strategies";
import { reviewsRoute } from "@/routes/reviews";

export const routeTree = rootRoute.addChildren([indexRoute, reviewsRoute, replyStrategiesRoute]);
