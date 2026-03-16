import { RotateCcw, Truck } from "lucide-react";
import { Separator } from "../ui/separator";

const DeliveryInfo = () => {
  return (
    <div className="rounded-xl border border-gray-200 bg-white">
      {/* Phần 1: Free Delivery */}
      <div className="flex items-start gap-4 p-5">
        <div className="mt-1">
          {/* Màu cam đặc trưng của các sàn TMĐT */}
          <Truck className="h-6 w-6 text-orange-500" />
        </div>
        <div className="space-y-1">
          <h3 className="font-bold text-sm md:text-base text-gray-900">
            Free Delivery
          </h3>
          <p className="text-xs md:text-sm text-gray-600">
            <span className="underline cursor-pointer hover:text-emerald-700 transition-colors">
              Enter your Postal code for Delivery Availability
            </span>
          </p>
        </div>
      </div>

      {/* Dùng Separator của Shadcn */}
      <Separator className="bg-gray-200" />

      {/* Phần 2: Return Delivery */}
      <div className="flex items-start gap-4 p-5">
        <div className="mt-1">
          <RotateCcw className="h-6 w-6 text-orange-500" />
        </div>
        <div className="space-y-1">
          <h3 className="font-bold text-sm md:text-base text-gray-900">
            Return Delivery
          </h3>
          <p className="text-xs md:text-sm text-gray-600">
            Free 30days Delivery Returns.{" "}
            <span className="underline font-medium cursor-pointer hover:text-emerald-700 transition-colors">
              Details
            </span>
          </p>
        </div>
      </div>
    </div>
  );
};

export default DeliveryInfo;
